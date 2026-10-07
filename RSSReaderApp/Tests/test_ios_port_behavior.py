"""Behavior checks against the actual ported Swift model and CloudKit merge code.

The fixture supplies only unrelated app dependencies. It never starts CloudKit,
registers push, opens UI, or sends network requests.
"""
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

STUBS = r'''
import Foundation
func syncLog(_ message: @autoclosure () -> String) {}
struct CoreAIMLXLocalService {
    static let defaultModelRepo = "test/model"
    static let defaultContextTokens = 2048
    static let maxContextTokens = 8192
    static func normalizedModelID(_ value: String) -> String { value }
}
struct MLXLocalService {
    static func normalizedModelIdentifier(from value: String) -> String { value }
}
enum LocalTTSEngine: String, Codable { case system }
enum KokoroVoice: String, Codable { case test; static let defaultVoice = Self.test }
enum ChatGPTPlanAvailability { static let isEnabled = true }
final class ReadRecencyStore {
    static let shared = ReadRecencyStore()
    func newest(_ ids: Set<String>, limit: Int) -> Set<String> { Set(ids.prefix(limit)) }
}
'''

PROBE = r'''
extension CloudKitSyncManager {
    static func exerciseConflictOrdering() {
        let manager = CloudKitSyncManager()
        manager.data = LocalData()
        let name = favoriteRecordName(.article, "article-1")
        func favorite(_ state: Bool, _ time: Double) -> CKRecord {
            manager.record(for: name, payload: .favorite(.article, "article-1", isFavorite: state, changedAt: Date(timeIntervalSince1970: time)))
        }
        let first = manager.changes(from: [favorite(true, 10)])
        precondition(!first.isEmpty)
        let removal = manager.changes(from: [favorite(false, 20)])
        guard case .favorites(.article, let added, let removed, _) = removal.first else {
            preconditionFailure("Favorite removal was not delivered")
        }
        precondition(added.isEmpty && removed == ["article-1"])
        precondition(manager.changes(from: [favorite(true, 15)]).isEmpty, "Stale favorite restored a removal")
        precondition(manager.changes(from: [favorite(true, 20)]).isEmpty, "Equal timestamp overwrote known state")
        precondition(!manager.changes(from: [favorite(true, 30)]).isEmpty, "A newer user re-favorite was rejected")

        let sub = Subscription(title: "Feed", url: "https://example.com/feed", type: .rss)
        let key = subscriptionRecordName(sub.canonicalKey)
        func subscription(_ deleted: Bool, _ time: Double) -> CKRecord {
            manager.record(for: key, payload: .subscription(sub, isDeleted: deleted, changedAt: Date(timeIntervalSince1970: time)))
        }
        _ = manager.changes(from: [subscription(false, 10)])
        let deleted = manager.changes(from: [subscription(true, 20)])
        guard case .subscriptions(let upserted, let removedKeys, _) = deleted.first else {
            preconditionFailure("Subscription removal was not delivered")
        }
        precondition(upserted.isEmpty && removedKeys == [sub.canonicalKey])
        precondition(manager.changes(from: [subscription(false, 15)]).isEmpty, "Stale subscription restored a removal")
    }
}

@main struct Probe {
    static func main() throws {
        let legacy = try JSONDecoder().decode(AppSettings.self, from: Data(#"{"selectedSummaryProvider":"Apple PCC Gateway","refreshInterval":60}"#.utf8))
        precondition(legacy.selectedSummaryProvider == .applePCCGateway)
        precondition(legacy.openAICompatibleBaseURL.isEmpty)
        precondition(legacy.openAICompatibleMaxTokens == AppSettings.defaultOpenAICompatibleMaxTokens)
        precondition(legacy.redditGrantedScopes.isEmpty)
        var settings = legacy
        settings.openAICompatibleBaseURL = "http://127.0.0.1:1234/v1"
        settings.openAICompatibleModelID = "local-model"
        settings.openAICompatibleAPIKey = "fixture-secret"
        settings.openAICompatibleDisableThinking = true
        let encoded = try JSONEncoder().encode(settings)
        precondition(!String(decoding: encoded, as: UTF8.self).contains("fixture-secret"), "API key was persisted outside Keychain")
        let decoded = try JSONDecoder().decode(AppSettings.self, from: encoded)
        precondition(decoded.openAICompatibleBaseURL == settings.openAICompatibleBaseURL)
        precondition(decoded.openAICompatibleModelID == settings.openAICompatibleModelID)
        precondition(decoded.openAICompatibleDisableThinking)
        precondition(AppSettings.normalizedCoreAIMLXOutputTokens(100000, contextTokens: 8192) == 512)
        precondition(AppSettings.normalizedOpenAICompatibleMaxTokens(-1) == 256)

        let direct = URL(string: "https://i.redd.it/abc.jpg")!
        let preview = URL(string: "https://preview.redd.it/title-v0-abc.png?width=640&amp;format=webp")!
        precondition(RedditPost.imageIdentityKey(for: direct) == RedditPost.imageIdentityKey(for: preview))
        let post = RedditPost(id: "p", title: "Post", content: "", url: direct, publishDate: Date(), author: "a", subreddit: "s", score: 1, commentCount: 0,
            preview: Preview(images: [PreviewImage(source: PreviewSource(url: preview.absoluteString, width: 640, height: 480), resolutions: [])], enabled: true))
        precondition(post.bestImageURL == direct)
        precondition(post.allImageURLs.count == 1)
        let explanation = buildAskAISelectionPrompt(selectedText: "a metaphor", extractedContext: "nearby evidence", sourceContext: "original evidence", explainSelection: true)
        precondition(explanation.hasPrefix("Explain what the selected passage means"))
        precondition(explanation.contains("nearby evidence") && explanation.contains("original evidence"))
        let webPrompt = buildAskAISelectionPrompt(selectedText: "a metaphor", extractedContext: "nearby evidence", sourceContext: "original evidence", explainSelection: false)
        precondition(webPrompt.hasPrefix("Answer the question"))
        CloudKitSyncManager.exerciseConflictOrdering()
        print("settings compatibility, secret storage, limits, media identity, and CloudKit removal ordering passed")
    }
}
'''


@unittest.skipUnless(shutil.which("xcrun"), "Requires the macOS Swift compiler")
class IOSPortBehaviorTests(unittest.TestCase):
    def test_ported_settings_media_and_cloud_conflicts(self):
        sources = [
            ROOT / "Models/Models.swift",
            ROOT / "Models/RedditCommentModels.swift",
            ROOT / "Services/CloudKitSyncManager.swift",
        ]
        with tempfile.TemporaryDirectory(prefix="rss-mac-port-test-") as temp:
            temp = pathlib.Path(temp)
            fixture = temp / "Fixture.swift"
            components = (ROOT / "Views/AskAIComponents.swift").read_text()
            prompt_function = re.search(r"(?ms)^func buildAskAISelectionPrompt\(\n.*?^\}", components)
            self.assertIsNotNone(prompt_function)
            fixture.write_text(STUBS + "\n" + "\n".join(p.read_text() for p in sources) + "\n" + prompt_function.group(0) + PROBE)
            result = subprocess.run(
                ["xcrun", "swiftc", "-parse-as-library", "-swift-version", "5", "-module-cache-path", str(temp / "ModuleCache"), str(fixture), "-o", str(temp / "probe")],
                capture_output=True, text=True, timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            run = subprocess.run([str(temp / "probe")], capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("CloudKit removal ordering passed", run.stdout)


if __name__ == "__main__":
    unittest.main()
