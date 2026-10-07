"""Exercise the real macOS storage resolver and cleanup on disposable fixture trees."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def harness_source(source):
    types = source[source.index('struct LocalModelStorageItem:'):source.index('// MARK: - Inline Global Summary')]
    cache = source[source.index('    func getCacheSize()'):source.index('    #if os(macOS)\n    private func macAppStorageLocations()')]
    sizing = source[source.index('    private func macAppStorageSize('):source.index('    private func collectAppStorageBreakdownItems()')]
    sizing = sizing.rsplit('    #endif', 1)[0]
    rows = source[source.index('    private func collectAppStorageBreakdownItems()'):source.index('    private func directorySize(at url:')]
    storage = source[source.index('    private func directorySize(at url:'):source.index('    // MARK: - OPML Import')]
    methods = (cache + sizing + rows + storage).replace('private func ', 'func ')
    return '''import Foundation
''' + types + '''
private enum CoreAIMLXLocalService {
    static func normalizedModelID(_ value: String) -> String { value }
}
private struct TestSettings { let coreAIMLXModelID = "org/selected" }
private final class StorageProbe {
    let home: URL
    let temporary: URL
    let settings = TestSettings()
    init(home: URL, temporary: URL) { self.home = home; self.temporary = temporary }
    func macAppStorageLocations() -> [MacAppStorageLocation] {
        MacAppStorageScope.locations(home: home, temporaryDirectory: temporary,
            bundleID: "com.example.RSSReaderApp", modelIDs: [settings.coreAIMLXModelID, "mlx-community/pocket-tts"])
    }
''' + methods + '''
}
let root = URL(fileURLWithPath: CommandLine.arguments[1])
private let probe = StorageProbe(home: root.appendingPathComponent(CommandLine.arguments[2]), temporary: root.appendingPathComponent("tmp"))
switch CommandLine.arguments[3] {
case "caches": _ = probe.cleanStorageBreakdownItem(.caches)
case "temporary": probe.clearTemporaryDirectory()
case "failed-models": _ = probe.removeFailedModelDownloadFiles()
case "row": _ = probe.cleanStorageBreakdownItem(.caches, selectedURL: probe.home.appendingPathComponent("Library/Caches/YouTubeTranscripts"))
default: break
}
let result: [String: Any] = [
    "rows": probe.collectAppStorageBreakdownItems().map { ["id": $0.id, "bytes": $0.sizeBytes, "model": $0.isModelStorage] as [String: Any] },
    "models": probe.collectLocalModelStorageItems().map { $0.name },
    "cacheSize": probe.getCacheSize()
]
print(String(decoding: try JSONSerialization.data(withJSONObject: result), as: UTF8.self))
'''


class AppStorageScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='rss-storage-test-build-')
        source = Path(os.environ.get('RSS_STORAGE_TEST_SOURCE', ROOT / 'RSSReaderApp/Controllers/AppState.swift')).read_text()
        program = Path(cls.build.name) / 'StorageProbe.swift'
        program.write_text(harness_source(source))
        cls.binary = Path(cls.build.name) / 'StorageProbe'
        compiled = subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(Path(cls.build.name) / 'modules'), str(program), '-o', str(cls.binary)], capture_output=True, text=True)
        if compiled.returncode:
            cls.build.cleanup()
            raise AssertionError(compiled.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix='rss-storage-fixture-')
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name)
        self.home = 'home'

    def file(self, relative, size=128):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'x' * size)
        return path

    def run_probe(self, action='list'):
        result = subprocess.run([str(self.binary), str(self.root), self.home, action], check=True, capture_output=True, text=True)
        return json.loads(result.stdout.splitlines()[-1])

    def test_shared_user_folders_are_excluded_and_network_cache_is_not_double_counted(self):
        owned = self.file('home/Library/Caches/com.example.RSSReaderApp/Cache.db', 1_048_576)
        self.file('home/Library/Preferences/com.example.RSSReaderApp.plist', 256)
        for path in ['home/Documents/personal', 'home/Library/Application Support/OtherApp/data', 'home/Library/Caches/OtherApp/data', 'home/Library/WebKit/OtherApp/data', 'home/Library/Logs/other.log', 'home/Library/Caches/com.onevcat.Kingfisher.ImageCache.default/shared', 'tmp/codex-clipboard.jpg']:
            self.file(path, 2_097_152)
        result = self.run_probe()
        self.assertEqual(result['cacheSize'], '1.0 MB')
        self.assertEqual(sum(row['bytes'] for row in result['rows']), 1_048_576 + 256)
        self.assertIn(str(owned.parent), [row['id'] for row in result['rows']])

    def test_only_configured_models_are_listed_and_failed_download_cleanup_preserves_others(self):
        selected = 'home/.cache/huggingface/hub/models--org--selected'
        self.file(selected + '/weights.safetensors', 300)
        partial = self.file(selected + '/weights.partial', 25)
        unrelated = self.file('home/.cache/huggingface/hub/models--other--model/weights.partial', 800)
        self.file('home/.cache/huggingface/hub/models/another/repo/weights.safetensors', 900)
        self.file('home/.cache/huggingface/hub/models--mlx-community--pocket-tts/model.safetensors', 400)
        self.assertCountEqual(self.run_probe()['models'], ['org/selected', 'mlx-community/pocket-tts'])
        result = self.run_probe('failed-models')
        self.assertFalse(partial.exists())
        self.assertTrue(unrelated.exists())
        self.assertEqual(sum(row['bytes'] for row in result['rows']), 700)

    def test_cleanup_preserves_other_apps_files_and_only_removes_the_selected_row(self):
        owned = self.file('home/Library/Caches/com.example.RSSReaderApp/cache', 100)
        transcript = self.file('home/Library/Caches/YouTubeTranscripts/video.json', 200)
        other = self.file('home/Library/Caches/OtherApp/cache', 300)
        model = self.file('home/.cache/huggingface/hub/models--org--selected/weights.safetensors', 400)
        self.run_probe('row')
        self.assertFalse(transcript.exists())
        self.assertTrue(owned.exists())
        self.run_probe('caches')
        self.assertFalse(owned.exists())
        self.assertTrue(other.exists())
        self.assertTrue(model.exists())

    def test_temporary_cleanup_does_not_clear_the_shared_temporary_directory(self):
        owned = self.file('tmp/mlx_tts_12345678-1234-1234-1234-123456789abc.wav')
        unrelated = [self.file('tmp/codex-clipboard.jpg'), self.file('tmp/other-app/state'), self.file('tmp/shortcut_input_unrelated.txt')]
        self.run_probe('temporary')
        self.assertFalse(owned.exists())
        self.assertTrue(all(path.exists() for path in unrelated))

    def test_symlinked_storage_is_not_treated_as_app_owned(self):
        other = self.file('home/Library/Caches/OtherApp/cache', 100)
        (other.parent.parent / 'com.example.RSSReaderApp').symlink_to(other.parent, target_is_directory=True)
        self.assertEqual(self.run_probe()['rows'], [])
        self.run_probe('caches')
        self.assertTrue(other.exists())

    def test_sandbox_container_counts_only_private_data_without_duplicate_image_cache(self):
        self.home = 'home/Library/Containers/com.example.RSSReaderApp/Data'
        self.file(self.home + '/Documents/article', 100)
        self.file(self.home + '/Library/Caches/cache', 200)
        self.file(self.home + '/Library/Caches/com.onevcat.Kingfisher.ImageCache.default/image', 300)
        self.file('home/Documents/personal', 4_096)
        self.file('tmp/unrelated', 4_096)
        result = self.run_probe()
        self.assertEqual(sum(row['bytes'] for row in result['rows']), 600)
        self.assertEqual(len(result['rows']), 3)


if __name__ == '__main__':
    unittest.main()
