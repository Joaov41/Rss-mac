# Handoff: Port the iOS RSSum features into the native Mac app

Written 2026-10-07. This document is for an agent picking up the work cold.

## 1. Goal

The native Mac app at `/Volumes/screen/rss mac copy` was last updated in August and is far behind the iOS app. The task is to **port the iOS features into the Mac project** while keeping the Mac-only work the Mac app already has. The Mac app should end up with:

- the same sync behaviour as iOS
- the same AI providers
- the same feature set

It must still look and behave like a Mac app.

This is **not** a "replace the Mac folder with the iOS folder" job. The Mac project has a lot of Mac-specific code that iOS does not have (see section 5).

## 2. The two codebases

| | iOS (source of truth for new features) | Mac (target) |
|---|---|---|
| Path | `/Volumes/screen/rss latest ios27 - UI fix copy` | `/Volumes/screen/rss mac copy` |
| GitHub | `Joaov41/Rss` (public), branch `main`, HEAD `f041a4d` | `Joaov41/Rss-mac`, branch `codex/checkpoint-before-summary-state-fix-20260709`, HEAD `0cc061c3c` |
| Swift files | 58 | 50 |
| Bundle ID | `com.joaovalente.RSSReaderApp` | `com.joaovalente.RSSReaderApp` (same, so it shares iCloud data with iOS) |
| Deployment | iOS 26 | macOS 26 |

The iOS project also has its own macOS target, `com.example.RSSReaderApp`, built from the shared code with `#if os(macOS)` branches. **That is not the shipping Mac app.** Do not work in it. The Mac app is the separate project above.

### ⚠️ The Mac folder has a lot of uncommitted work. Commit it first.

`git status` in the Mac folder shows:

- **Modified, not committed:** 32 files (+5459 / −3649 lines). Includes `AppState`, `ContentView`, `RedditDetailView`, `SettingsView`, `CloudSyncManager`, `PersistenceManager`, `project.pbxproj`, and others.
- **Untracked:**
  - `Services/PodcastBackgroundTaskManager.swift`
  - `Services/PodcastDiscoveryService.swift`
  - `Services/PodcastEpisodeService.swift`
  - `Services/PodcastGeminiTextService.swift`
  - `Views/PodcastEpisodePlayerView.swift`
  - `Views/PodcastSearchView.swift`
  - `Packages/EventSource`, `Packages/FluidAudio`, `Packages/mlx-swift-compat`, `Packages/mlx-swift-lm-compat`
  - Python regression tests in `RSSReaderApp/Tests/`
  - `script/build_and_run.sh`
- **Deleted:** `Services/LiteRTLocalService.swift`

**Step 0, before touching any code:**

1. Make a checkpoint commit of the Mac folder exactly as it is now, on a new branch such as `mac-port-baseline`. Do not include `xcuserdata`, `.DS_Store`, `__pycache__`, `.codex-checkpoints/`, the stray file named `:-`, or `Website-Screenshots/`.
2. Do **not** push to GitHub without asking the user.
3. Then create a working branch such as `mac-port-ios-features`.

Git is the only safety net. Earlier scratch backups were wiped.

### ⚠️ Disk space

`/Volumes/screen` has **about 1.2 GB free**. A Mac build with MLX packages can fill that. Before building:

- Point DerivedData somewhere else with `-derivedDataPath`, on a volume with room, for example `/Volumes/BackUP /DerivedData-rssmac`.
- Ask the user before deleting anything to free space.

## 3. House rules from the user

- **The iOS folder is READ-ONLY.** Read and copy from it; never edit, build in, commit to, or run git commands that change it. (It's checkpointed at tag `checkpoint-before-mac-port-2026-10-07` and copied to `/Volumes/BackUP /rss-ios-checkpoint-2026-10-07`.)

- **Build only when the user asks.** Editing code is fine. Do not run `xcodebuild` or install builds unprompted. A compile check right before telling the user it is ready is fine if they asked for a build.
- Codex/Summarize and the Apple PCC Gateway are **hidden from the Settings provider list on iOS**. The code stays. Do the same on the Mac, unless the Mac copy needs them (see 5.4) — ask the user.
- The RSS repos are **public**. Before any push, scan for API keys, tokens and personal data.
- Keep code compatible with **older app versions that are already on the App Store**. iCloud key-value keys written by older builds must still be read, and the new code must keep writing what old builds need (see 4.1).
- When something is ambiguous (for example, which of two different implementations of the same feature to keep), ask the user. Do not pick silently.

## 4. What the Mac is missing, by priority

Start each item by reading the iOS file. Copy whole files where the file is new. Merge by hand where both sides changed. A symbol-level diff of every shared file is in **Appendix A**.

### 4.1 Sync (P0, do first)

This matters most. Mac and iOS share the bundle ID, so they share the same iCloud key-value store. Today the Mac writes the **old** format (primary device, legacy favorites and subscription keys). That can fight with the iOS rework.

**Bring over from iOS:**

- **`Services/CloudKitSyncManager.swift`** (new, 758 lines; whole file):
  - Uses `CKSyncEngine` on the private database: zone `RSSumSync`, container `iCloud.com.joaovalente.RSSReaderApp`.
  - Stores one record per read item, favorite and subscription.
  - Favorites and subscriptions carry a state and a `changedAt`. `acceptIfNewer` makes the newest change win.
  - Records are never deleted, so stale uploads cannot bring back removed items.
  - Status text for Settings comes from `friendlyStatus()` and `statusSummary()`.
  - Expected conflicts (code 14, "record already exists") are filtered out of "Last error".
- **`Services/CloudSyncManager.swift`** (iOS 1432 lines vs Mac 1176). Take the iOS version and re-add only Mac-specific bits that still make sense. iOS has, and the Mac lacks:
  - `syncLog` (debug-only logging)
  - `ReadRecencyStore`
  - the per-device favorite event store (`FavoriteKind`, `FavoriteEvent`, `recordFavorite`, `seedFavoriteRecords`, `effectiveFavorites`, `mergedFavoriteEvents`, …), using keys `cloud_v2_favArticles_` and `cloud_v2_favReddit_`
  - per-feed subscription records (`recordSubscriptionChanges`, `seedSubscriptionRecords`, `effectiveSubscriptions`, `subscriptionRecords`, …), using `sbv1_` keys
  - quota cleanup that keeps the most recent read history (1 MB and 1,024-key limits)

  **iOS deliberately removed**, and the Mac still has:
  - primary device (`isThisDevicePrimary`, `setThisDeviceAsPrimary`, `primaryDeviceName`, …)
  - `syncFavoriteArticles`, `syncFavoriteRedditPosts`, `syncSubscriptions`, `forceSyncSubscriptions`
  - `migrateLegacyReadHistoryToV2`

  Remove these on the Mac too. The user explicitly asked for "no primary device" and "remove Migrate Read History".
- **`Services/PersistenceManager.swift`.** iOS adds:
  - the `cloudKit` hook
  - `isOnlyDefaultSubscriptions` (a list that is only the defaults is never uploaded)
  - `seedCloudRecordsIfReady`
  - `mergedFavorites` and `mergedSubscriptions` with tombstones (`favoriteTombstoneKey`, `tombstones`, `setTombstone`)
  - `applyCloudKitFavorites` and `applyCloudKitSubscriptions`

  The Mac has `…PrimaryForSubscriptions` and `mergeSubscriptions`; remove them. Keep `backfillReadTokensIfNeeded` only if nothing on the iOS side replaced it; check its callers.
- **`Controllers/AppState.swift`.** Port:
  - `handleCloudKitChange` and `legacyChangeMatchesLastSnapshot`
  - `scheduleCloudUIUpdates`, `computeCloudPollDiff`, `applyCloudPollDiff`
  - `CloudPollDiff`, `CloudUIUpdateKind`, `ArticleReadProbe`, `RedditReadProbe`
  - `cloudPollQueue`, `lastCloudSnapshot`, `manualCloudStateChanged`

  The Mac has its own unread-cache code (`rebuildUnreadCachesFromInMemoryFlags`, `scheduleUnreadCacheRebuild`, `syncAllReadStatesFromPersistence`). Make sure the CloudKit change path triggers that rebuild so Mac badge counts update.
- **`RSSReaderApp.swift`.** iOS added an app delegate (`RSSReaderAppDelegate`) for remote notifications, which CloudKit push needs. On the Mac this must be an `NSApplicationDelegate`, attached with `@NSApplicationDelegateAdaptor`, that:
  - calls `NSApplication.shared.registerForRemoteNotifications()`
  - forwards `application(_:didReceiveRemoteNotification:)`
- **Settings sync UI.** iOS shows a plain sync status with collapsible details, and has no primary-device section and no Migrate Read History. On the Mac:
  - delete `isMigratingReadHistory`, `startReadHistoryMigration`, the migration confirmation, and the primary-device UI from `SettingsView.swift`
  - add the iOS sync status block, styled with the Mac's `settingsGlassPanel` helpers

**Entitlements for the Mac.** Edit `RSSReaderApp/RSSReaderApp.entitlements`. Keep everything already there and add:

```xml
<key>com.apple.developer.aps-environment</key>
<string>development</string>   <!-- production for App Store builds -->
<key>com.apple.developer.icloud-container-identifiers</key>
<array><string>iCloud.com.joaovalente.RSSReaderApp</string></array>
<key>com.apple.developer.icloud-services</key>
<array><string>CloudKit</string></array>
```

On macOS the push key is `com.apple.developer.aps-environment`, not `aps-environment` as on iOS. The iOS files to compare against are `RSSReaderApp/RSSReaderApp (iOS)Debug.entitlements` and `RSSReaderApp (iOS)Release.entitlements`.

The App ID already has iCloud/CloudKit, because iOS uses the same bundle ID. Xcode signing may still need the iCloud capability ticked on the Mac target; tell the user if signing complains.

**CloudKit schema.** The record types were created in the Development environment by the iOS builds. Before a Mac App Store release, the user must deploy the schema to Production in the CloudKit Console. Remind them; do not attempt it.

### 4.2 AI providers (P1)

- **Custom Server (OpenAI-compatible)**, for oMLX, Ollama, LM Studio, llama.cpp and similar. Copy these files whole:
  - `Services/OpenAICompatibleService.swift`
  - `Controllers/AppState+OpenAICompatible.swift`
  - `Views/OpenAICompatibleSettingsView.swift`

  Then wire it in:
  - **`Models.swift`:** add the settings fields `openAICompatibleBaseURL`, `openAICompatibleAPIKey`, `openAICompatibleModelID`, `openAICompatibleMaxTokens` and `openAICompatibleDisableThinking`. Also add `defaultOpenAICompatibleMaxTokens`, `normalizedOpenAICompatibleMaxTokens`, the custom `encode`/decode with defaults so old saved settings still decode, `case openAICompatible` in the provider enum, and `hiddenCases`.
  - **`SummarizeBridge.swift`:** add `openAICompatibleAPIKeyKey` and the chat-completion request/response structs if `OpenAICompatibleService` depends on them.
  - **Every provider `switch`:** article summary, Reddit summary, Q&A, Ask AI on a selection, overall summary, comment summary, and podcast text. In iOS, search for `.openAICompatible` and mirror each site.
  - **Mac UI text:** the iOS help text says "On iPhone and iPad, enter your Mac's network address". On the Mac, `http://127.0.0.1:<port>/v1` works. The Mac already has `com.apple.security.network.client`, which outgoing HTTP to localhost needs.
- **ChatGPT Plan provider.** Copy:
  - `Services/ChatGPTPlanService.swift`
  - `Controllers/AppState+ChatGPTPlan.swift`
  - `Views/ChatGPTPlanSettingsView.swift`

  Add `case chatGPT` to the enum and wire it the same way. Check with the user whether they want it on the Mac. On iOS it is visible, but in redapp the equivalent is a local-only gate.
- **Provider visibility.** iOS hides Codex/Summarize and the PCC Gateway with `hiddenCases`. The Mac's `macSummaryProviderSelector` and `macSummaryProviderTitle` in `SettingsView.swift` need the same filter.

### 4.3 Background work and resilience (P1, mostly not needed on Mac, read carefully)

iOS uses `BGContinuedProcessingTask` heartbeats so long model calls survive the app being backgrounded. **macOS does not suspend apps that way.** Do **not** port these as they are:

- `GeminiBackgroundTaskManager.swift`
- the iOS `PodcastBackgroundTaskManager.swift` (593 lines vs the Mac's 90-line `ProcessInfo` activity version)

What to do instead:

- Keep the Mac's `PodcastBackgroundTaskManager` (it uses `ProcessInfo.beginActivity`).
- Where iOS calls `GeminiBackgroundTaskManager` or uses `globalBackgroundHandle`, `webAIBackgroundHandle`, `syncWebAIBackgroundWork` or `generationBackgroundHandle` (in `BatchPodcastSession`), either:
  - add a tiny Mac shim with the same API that wraps `ProcessInfo.processInfo.beginActivity(options: [.userInitiated, .idleSystemSleepDisabled], reason:)`, or
  - wrap those calls in `#if os(iOS)`.

  The shim is preferred, so `AppState` code can be copied from iOS with fewer edits.

The parts that **are** worth porting from this area:

- `SummaryService.withAIBackgroundTask`
- the Web AI request timeout and displacement logic: `webAIRequestTimeoutSeconds`, `displaceActiveWebAIRequestIfNeeded`, `makeWebAIRequestTimeoutWorkItem`, and `WebAIHandoffView.cancelActiveRequest` / `keepWebViewsAwake`
- the Reddit comment fetch retry and rate-limit backoff: `CommentFetchOutcome`, `fetchWithRetry`, `delayForRateLimitExhaustion`, `processBatch`, `processSequentially`, `monitorBatch`

**Reconcile the rate-limit code; do not duplicate it.** The Mac has its own, richer rate-limit tracking (`RedditRateLimitStatus`, `RedditStatusMessage`, `reserveRateLimitSlot`, …). iOS has a different one (`extractRateLimitInfo`, `handleRedditSummaryCooldown`, cooldown messages). Keep the Mac's unless the user says otherwise, and only add the iOS retry behaviour on top of it.

### 4.4 Features and UI (P2)

| Feature | iOS location | Mac notes |
|---|---|---|
| **Mark All as Read** (long-press or right-click Reddit, All, Unread, Today, with confirmation) | `AppState.markAllAsRead(in:)`, `unreadCount(in:)`, `categoryFilters`; `ContentView` `MarkAllReadMenu` | On the Mac use `.contextMenu` on the sidebar rows (right-click) with a confirmation `.alert`. Hook into the Mac unread-cache rebuild. |
| **Overall Summary toolbar floats over the text** (scrolling never shifts or jumps) | commit `6b80e52`, `ContentView.swift` | Compare with `GlobalSummaryResultView.swift` (Mac-only). Apply the same overlay idea there; do not replace the Mac view. |
| **Scroll smoothness while models stream** | `onScrollPhaseChange` and the coalesced UI updates in `ContentView` / `RedditDetailView` | The Mac already uses `onScrollPhaseChange` in one place. Check whether streaming summaries jitter on the Mac before porting. |
| **Dark mode colours, option C** (navy-tinted sidebar, soft navy list gradient, dark navy reader column) | `ContentView.swift` colour constants (commit `f041a4d`) | The Mac uses `macDynamicColor` / `rgb` helpers. Port the colour **values**, not the UIKit code. The user likes the blue; do not turn it grey. |
| **Reddit: post a comment / reply** | `RedditService.commentOnPost`, `submittedComment`, `invalidateCommentCache`; `RedditOAuthManager` scopes and `hasReplyPermission`; `CommentViews` reply composer; `RedditDetailView.postCommentSheet` and `handleReplyPosted` | Needs the extra OAuth scope. Keep the Mac's `handleMacOSCallback` OAuth flow and add the scopes. Existing users will need to reconnect Reddit to grant the new scope. |
| **Reddit detail Q&A section and layout** | `RedditDetailView` `redditQASection`, `redditQAUtilityButtons`, `scrollToRedditQAIfNeeded` | The Mac has its own, bigger Q&A UI (`RedditQAActionButtonStyle`, `answerParagraphs`, …). Compare behaviour first; port only missing behaviour. |
| **Ask AI on a text selection** | `Views/AskAIUtilities.swift` (new), `runSelectionAskAI` in `SummaryColumnView`, `RedditDetailView`, `InfographicView` | The Mac already has its own version (`AskAIComponents.swift`, `askAIFromSummaryColumnSelection`, …). **Probably keep the Mac's.** Only port prompt or logic fixes: `executeSelectionPrompt`, `selectionAnswerPrompt`, `chunkedSelectionSources`, `globalSummarySelectionSourceContext`. |
| **Article full-text cache** | `FeedService.CachedArticleContent`, `fullArticleCache`, `cachedFullArticle`, `canonicalArticleURL`, the concurrency limit | Port as is; it's pure Foundation. Keep the Mac's anti-block and ad-stripping helpers. |
| **Reddit image URL fixes** | `Models.swift`: `resolvedImageURL`, `decodedRedditMediaURL`, `resolveBestRedditImageURL`, `imageIdentityKey`, `previewText` | Port as is. |
| **Podcast playback** (Now Playing, remote commands, interruptions) | `PodcastEpisodeService.configureRemoteCommands`, `updateNowPlayingInfo`, `handleInterruption`; `MLXPodcastPlaybackController` prepared audio and interruption handling | `MPRemoteCommandCenter` and `MPNowPlayingInfoCenter` work on the Mac (media keys, Control Center). `AVAudioSession` does not exist on macOS, so skip those parts. |
| **Podcast transcript discard and classification** | `AppState.schedulePodcastTranscriptDiscard`, `recordPodcastClassification`, `podcastSubscriptionCanonicalKeys` | Port. |
| **Refresh a single feed** | `AppState.refreshSingleRSSFeed` | Port. |
| **Navigation reset** | `resetNavigationHistory`, `exitActiveSubscriptionView` | Check against the Mac's `MainSplitView` and keyboard navigation (`handleBackKeyPress`). |
| **Overall summary provider fallback** | `OverallSummaryProviderResolution`, `resolveOverallSummaryProvider`, `overallSummaryProviderResolution`, `runArticlesGlobalSummary`, `runRedditGlobalSummary`, `beginSubredditGlobalSummary`, `processGlobalSummaryResult` | The Mac has `GlobalSummaryService.swift` and `aggregateSummaryProviderName`. Merge the fallback logic into the Mac service. Do not replace it. |
| **Apple Cloud JSON repair, MLX caps and timeouts** | `parseAppleCloudResponse`, `repairClosingDelimiters`, `cleanCloudJSON`, `fallbackSummaryResult`; MLX caps (`coreAIMLXMaxOutputTokenHardCap`, `withMLXTimeout`, `shouldRerouteLocalPrompt`) | Port. These are summary-robustness fixes. |
| **Latest News widget snapshot** | `Shared/LatestNewsStore.swift`, `LatestNewsSnapshotBuilder`, `scheduleLatestNewsSnapshotIfSupported` | There is no Mac widget target. **Skip** unless the user wants a Mac widget. |
| **Kokoro TTS playback helper** | `Utilities/KokoroPlayback.swift` | The Mac has its own Kokoro functions (`startKokoroPlayback…`, `firstReadAloudChunkLength`). Compare; probably skip. |
| **iPhone-only layout** (`horizontalSizeClass`, compact layouts, iPhone favorite star, the Add Subscription type menu) | various | **Skip the size-class parts.** Do port the Add Subscription type **menu** idea into the Mac's own `Views/AddSubscriptionView.swift` if the Mac still uses a different picker; ask the user. |

### 4.5 Tests

iOS has `Tests/BatchPodcastTests.swift` and `Tests/YouTubeSupportTests.swift`. The Mac uses Python source-level regression tests in `RSSReaderApp/Tests/*.py`.

- Keep the Python tests passing: `python3 -m pytest RSSReaderApp/Tests`, or run each file. Several of them assert that Mac-specific code exists, so they catch Mac work removed by accident.
- Add the Swift tests only if the Mac project has a test target.

## 5. Mac-only work to keep (do not overwrite)

### 5.1 Files that only exist on the Mac

- `Models/GlobalSummaryModels.swift`
- `Services/GlobalSummaryService.swift`
- `Views/GlobalSummaryResultView.swift`
- `Views/AddSubscriptionView.swift`
- `Views/AskAIComponents.swift`

### 5.2 Mac-only code inside shared files

From Appendix A. Do not lose any of this when you merge.

- **`AppState`:**
  - `MacAppStorageLocation`, `MacAppStorageScope`, `isAppTemporaryFile` (storage management)
  - `RedditStatusMessage` and the rate-limit status UI state
  - the Reddit feed sort cache (`redditFeedSortState`, `redditFeedSortCache`, `ensureRedditFeedMatchesCurrentSort`)
  - the unread-cache rebuild functions
  - `fullArticleContext`, `localBoundedArticleContext`, `articleFullContextSummaryPrompt`, `articleFullQAPrompt`
  - Web AI echo detection (`isWebAIPromptEchoResponse`)
  - `generateBatchPodcastLocalText`
  - global summary state
- **`ContentView`:**
  - `MacNavigationSwipeView` / `SwipeCaptureView`: trackpad back and forward. This **replaces** iOS's `TrackpadScrollGestureOverlay`; do not port the iOS one.
  - keyboard back and forward
  - `macDynamicColor`
  - Mac clipboard helpers
  - the `MacNativeScroll…` / `MacArticleScroll…` web-view scroll restoration and reporting
- **`SummarizeBridge`:** the whole `fm` CLI and Terminal-helper path (`runFM`, `runFMViaTerminalHelper`, `ensureTerminalHelperStarted`, `cleanFMResponse`, …). This is how the Mac reaches Apple Foundation Models / PCC. It needs the `.summarize/daemon.json` temporary-exception entitlement and `network.server`. Keep all of it.
- **`SummaryService`:** `speakViaURLScheme`, `speakViaCLI`, `CLIJob` (Mac Shortcuts TTS).
- **`SettingsView`:** the `MacSettings…` glass styles, `settingsNavigationContainer`, `macSummaryProviderSelector`, `macWebAISelector`, `macWebAISessionButtons`.
- **`RedditService`:** the full rate-limit system, subreddit icon cache, `cleanedIconURL`.
- **`RedditOAuthManager`:** the macOS callback flow (`handleMacOSCallback`, `pendingAuthState`).
- **`CommentViews`:** the Mac comment layout (`formatCommentBodyBlocks`, `extractNonImageLinks`, `actionsFitOnHeaderLine`, the Mac reply views).
- **`RedditDetailView`:** the Mac single-column layout, the Mac speech and Kokoro summary playback, `RedditCommentsActionPillModifier`.
- **`FeedService`:** the anti-block and ad-stripping helpers.
- **`YouTubePlayerView`:** `YouTubeScrollForwardingWebView` (NSView).
- **`InfographicView`:** the Mac Ask AI and edit-menu path.
- **`BatchPodcastView`:** `presentSavePanel` (`NSSavePanel`). The iOS `UIDocumentPicker` exporter is iOS-only.
- **`AudioUtils`:** the `NSSpeechSynthesizer` voices.
- **`PlatformViews`:** `AdaptiveGlassModifier`.
- **`PodcastEpisodePlayerView`:** `PodcastTimestampCitationView`.
- **`MainSplitView`:** the settings button and sheet, `sortedArticles`.

### 5.3 Mac `.codex-checkpoints/` and the `.md` guides

The Mac folder contains `.codex-checkpoints/` and several untracked `.md` guides. Leave them in place. Do not commit `.codex-checkpoints/`.

### 5.4 Ask the user

The Mac's way into Apple Foundation Models (the `fm` CLI bridge) may be the reason the Mac still needs the "Codex/Summarize" or PCC entries. Ask before hiding them on the Mac.

## 6. Suggested order of work

1. Step 0: checkpoint commit and branch (section 2).
2. Run the Python regression tests to get a baseline.
3. Sync (4.1): files, entitlements, delegate, settings. **Ask the user for a build**, then test sync between the Mac and the iPad (section 7).
4. Custom Server, then ChatGPT Plan if wanted (4.2). Ask the user for a build, then test against a local LM Studio, Ollama or oMLX server.
5. Summary robustness: JSON repair, MLX caps, overall-summary fallback, Reddit fetch retry (4.3 and 4.4).
6. Mark All as Read, dark colours, Overall Summary toolbar overlay (4.4).
7. Reddit comment posting (4.4), which needs a Reddit reconnect.
8. Podcast Now Playing, article cache, image URL fixes, and the rest of 4.4.
9. Python tests, then hand back to the user for a full build and a manual pass.

Commit after each step with a clear message, so any step can be reverted alone.

## 7. How to verify

The user tests on these devices:

- **iPad M1:** the main sync partner.
- **iPhone 14 Pro**
- **iPhone 17 Pro:** its key-value sync is broken at the device level, so **don't use it to judge sync** and don't spend time on it.

### Sync checks, Mac ↔ iPad

1. Settings shows the CloudKit status as available or synced, with no "record already exists" errors.
2. Mark an article read on the Mac. It shows as read on the iPad within about a minute, and the other way round.
3. Favourite an article and a Reddit post on the Mac. They appear on the iPad. Unfavourite on the iPad; they disappear on the Mac and **do not come back** after relaunching both apps.
4. Add a subscription on the Mac and it appears on the iPad. Remove it on the iPad and it stays removed on the Mac.
5. Fresh-install check: a Mac with only the default subscriptions must **not** overwrite the iPad's list.
6. Unread badge counts on the Mac sidebar update after remote changes.

### Provider checks

- **Custom Server:** Test Connection lists models; an article summary, a Reddit summary, Q&A and an overall summary all work; the throughput label shows the model name.
- **Hidden providers:** they no longer show in the Settings picker, but a user who had one selected still works or falls back cleanly.

### UI checks

- **Mark All as Read:** right-click Reddit, All, Unread and Today; the confirmation appears; counts drop to zero.
- **Dark mode:** navy-tinted sidebar, navy list gradient, dark navy reader column.
- **Overall Summary:** the toolbar stays put while scrolling a long, streaming summary.
- **Trackpad and keyboard:** back and forward still work (the Mac-only code survived).

## Appendix A: symbol diff of shared files

This was generated by a script that pulls the names of top-level and first-level declarations out of each file, so it's approximate. `@N` is the line number in that file.

To regenerate it:

```bash
python3 script/ios_mac_symdiff.py   # paths to both trees are hard-coded at the top
```


**How to read it:** "iOS only" means candidates to port. "Mac only" means things to keep, or things iOS removed on purpose (see 4.1).

#### `Controllers/AppState.swift`
- **iOS only:** `class GeminiAggregateBackgroundContext@23`, `var handle@24`, `enum CodingKeys@77`, `struct OverallSummaryProviderResolution@92`, `let selectedProvider@93`, `let effectiveProvider@94`, `let localFallbackProviderName@95`, `func resolveOverallSummaryProvider@103`, `func setThroughputReporter@191`, `func setWarningReporter@196`, `func setRedditCommentsCacheReporter@201`, `func reportThroughput@205`, `func reportAppleLocalThroughput@211`, `struct CommentFetchOutcome@301`, `func processBatch@317`, `func delayForRateLimitExhaustion@323`, `func fetchWithRetry@336`, `func processSequentially@419`, `func reportBatchCompletion@506`, `func monitorBatch@515`, `func parseAppleCloudResponse@948`, `func isJSONLikeSummaryResponse@975`, `func normalizeAppleCloudResult@982`, `func decodeJSONStringIfNeeded@1016`, `func decodeStrictJSON@1021`, `func decodeJSON@1037`, `func repairClosingDelimiters@1055`, `func cleanCloudJSON@1072`, `func parseLooseSummaries@1107`, `func buildLooseResult@1129`, `func fallbackSummaryResult@1272`, `let coreAIMLXMaxOutputTokenHardCap@1355`, `let coreAIMLXMaxContextTokenHardCap@1356`, `let mlxInputCharacterLimit@1357`, `let mlxGenerationTimeoutSeconds@1358`, `let mlxQueryTimeoutSeconds@1359`, `func cappedMLXOutputTokens@1362`, `func cappedMLXContextTokens@1367`, `func optimizedPromptForMLX@1373`, `struct MLXTimeoutError@1378`, `func withMLXTimeout@1382`, `func buildArticlesPromptPublic@1605`, `func buildRedditPromptPublic@1610`, `case allArticles@1887`, `case allReddit@1888`, `case todayArticles@1889`, `case todayReddit@1890`, `case feedArticles@1891`, `case subreddit@1892`, `case subredditHot@1893`, `case subredditSorted@1894`, `let horizontalSizeClass@1943`, `func resetNavigationHistory@2077`, `func exitActiveSubscriptionView@2148`, `var aggregateSummaryTask@2249`, `var globalBackgroundHandle@2252`, `var cachedRedditCommentsForQA@2257`, `struct ArticleReadProbe@2418`, `struct RedditReadProbe@2426`, `struct CloudPollDiff@2433`, `let cloudPollQueue@2439`, `var isCloudPollInFlight@2440`, `struct CloudUIUpdateKind@2442`, `var pendingCloudUIUpdates@2452`, `var cloudUIUpdateScheduled@2453`, `var lastCloudSnapshot@2454`, `var podcastSubscriptionCanonicalKeys@2460`, `let webAIRequestTimeoutSeconds@2511`, `var webAIBackgroundHandle@2515`, `var webAIKeepAliveTimer@2516`, `func syncWebAIBackgroundWork@2519`, `var manualCloudStateChanged@2684`, `func handleCloudKitChange@2893`, `func legacyChangeMatchesLastSnapshot@2916`, `func scheduleCloudUIUpdates@2933`, `func computeCloudPollDiff@3078`, `func applyCloudPollDiff@3122`, `func recordPodcastClassification@3235`, `func refreshSingleRSSFeed@3391`, `func scheduleLatestNewsSnapshotIfSupported@3592`, `func pruneExpiredRedditCooldowns@3618`, `func activeCooldowns@3626`, `func formatCooldownDuration@3635`, `func formatCooldownReadyTime@3648`, `func makeCooldownMessage@3652`, `func handleRedditSummaryCooldown@3676`, `func displaceActiveWebAIRequestIfNeeded@3983`, `func makeWebAIRequestTimeoutWorkItem@4051`, `func flattenedFullCommentLinesForSummary@4379`, `func localArticleSummaryPrompt@4442`, `func localArticleQAPrompt@4545`, `func makeArticleQAPrompt@4554`, `func geminiRedditQAPrompt@4587`, `func globalSummarySelectionSourceContext@4644`, `func redditSelectionSourceText@4695`, `func flattenedCommentCountForSummary@4733`, `func combinedGlobalSummaryPrompt@4886`, `func schedulePodcastTranscriptDiscard@5445`, `func overallSummaryProviderResolution@6200`, `func prepareGlobalSummaryBackgroundHandleIfNeeded@6238`, `func runArticlesGlobalSummary@6294`, `func runRedditGlobalSummary@6317`, `func hydratedRedditFeed@6342`, `func recordRedditFetchMetadata@6371`, `func beginSubredditGlobalSummary@6408`, `func summarizeSubredditPostsGloballyInternal@6734`, `func processGlobalSummaryResult@6899`, `func cleanedText@7361`, `func launchShortcutViaXCallback@7660`, `func fallbackToXCallbackFromCLI@7799`, `var shortcutInputFileURL@7894`, `var shortcutOutputFileURL@7898`, `func writeShortcutInputFile@7902`, `func readShortcutOutputFile@7906`, `func clearShortcutOutputFile@7911`, `func targetArticleSummaryWordLimit@8117`, `func truncateSummaryBySentences@8128`, `func truncateToWordCount@8171`, `func countWords@8178`, `func cleanAndFormatSummaryTextForDisplay@8182`, `func cleanAndFormatRedditSummaryTextForDisplay@8219`, `func categoryFilters@9052`, `func markAllAsRead@9077`, `func showContextRerouteNotification@9228`, `func appleLocalUnavailableError@9397`, `func generateAppleLocalStreaming@9406`, `var selectedLocalModelLabel@9538`, `var selectedLocalModelID@9542`, `func generateLocalTextWithMetrics@9546`, `func clearLocalModelTransientCache@9572`, `let appStateCoreAIMLXMaxOutputHardCap@9724`, `let appStateCoreAIMLXMaxContextHardCap@9725`, `let appStateMLXGenTimeout@9727`, `let appStateMLXQueryTimeout@9728`, `func coreAIMLXLocalPromptFits@9747`, `func shouldRerouteLocalPrompt@9758`, `struct AppStateMLXTimeoutError@9860`, `var mlxGenerationTimeoutSeconds@9896`, `var mlxQueryTimeoutSeconds@9897`, `var interactiveAskAITimeoutSeconds@9898`, `func answerQuestion@9904`, `func generateMetrics@10243`, `func cappedMLXAnalysisOutputTokens@10363`, `func executeSelectionPrompt@11243`, `func selectionAnswerPrompt@11255`, `func normalizedSelectionText@11281`, `func chunkedSelectionSources@11290`, `struct LatestNewsSnapshotBuilder@11617`, `func buildSnapshot@11618`, `func makeSnippet@11661`, `func makeDeeplink@11679`, `func firstNonEmptyString@11686`, `func enrichItemsWithImages@11696`, `func fetchImageData@11716`, `func downscaleImageData@11739`
- **Mac only:** `struct MacAppStorageLocation@61`, `var isModelStorage@65`, `enum MacAppStorageScope@70`, `func locations@71`, `func isAppTemporaryFile@149`, `struct RedditStatusMessage@185`, `let subreddit@186`, `let text@187`, `let statusCode@188`, `let resetDate@189`, `let remaining@190`, `let capturedAt@191`, `var formattedReset@193`, `var redditStatusMessages@1527`, `var aggregatedRedditStatusMessage@1528`, `var lastGlobalSummaryContext@1604`, `var aggregateSummaryProviderName@1609`, `var globalSummaryComments@1621`, `func generateBatchPodcastLocalText@1728`, `var redditFeedSortState@1826`, `var redditFeedSortCache@1827`, `var isUnreadCacheRebuildScheduled@1828`, `func syncAllReadStatesFromPersistence@2130`, `func subscriptionCacheKey@2136`, `func rebuildUnreadCachesFromInMemoryFlags@2140`, `func scheduleUnreadCacheRebuild@2172`, `func unreadAllArticlesCount@2186`, `func unreadAllRedditCount@2190`, `func backfillReadTokensForVisibleReadItems@2457`, `func updateRedditRateLimitStatus@2468`, `func appendIfUnique@2483`, `func redditFeedCacheKey@2541`, `func cacheRedditFeed@2545`, `func hydratedCachedRedditFeed@2549`, `func ensureRedditFeedMatchesCurrentSort@2689`, `func ensureAllRedditFeedsMatchCurrentSort@2703`, `func clearRedditStatusMessages@2716`, `func normalizedWebAIComparisonText@3114`, `func webAIProbeMatchesPrompt@3121`, `func isWebAIPromptEchoResponse@3125`, `func fullArticleContext@3434`, `func localBoundedArticleContext@3445`, `func fullRedditContext@3449`, `func flatten@3450`, `func articleFullContextSummaryPrompt@3536`, `func articleFullQAPrompt@3643`, `func redditFullSummaryPrompt@3652`, `func redditFullQAPrompt@3661`, `func emptySummaryPlaceholder@5988`, `func errorSummaryJSON@5992`, `func handleSummaryResult@5997`, `func performArticlesSummary@6051`, `func performRedditSummary@6121`, `func summarizeTodayArticlesGlobally@6361`, `func summarizeTodayRedditGlobally@6377`, `func hydrateRedditFeed@6455`, `func subredditSummaryLabel@6518`, `func decodeGlobalSummaryResult@6631`, `func buildAggregatePrompt@6652`, `func launchAggregateSummary@6687`, `func loadCacheSize@7150`, `func macAppStorageLocations@7190`, `func macAppStorageSize@7200`, `func savedSummarySelectionPrompt@8733`, `func executeGlobalSelectionPrompt@8753`, `func globalSelectionAnswerPrompt@8765`, `func normalizedGlobalSelectionText@8779`, `func chunkedGlobalSelectionSources@8788`, `func formatLLMAnswer@9076`, `func selectedLocalProviderName@9256`, `func localPromptFits@9260`

#### `Models/Models.swift`
- **iOS only:** `var openAICompatibleBaseURL@34`, `var openAICompatibleAPIKey@35`, `var openAICompatibleModelID@36`, `var openAICompatibleMaxTokens@37`, `var openAICompatibleDisableThinking@38`, `var redditGrantedScopes@53`, `let defaultOpenAICompatibleMaxTokens@152`, `func normalizedOpenAICompatibleMaxTokens@154`, `func encode@304`, `case chatGPT@378`, `case openAICompatible@379`, `var available@386`, `var previewText@614`, `func makePreviewText@667`, `extension String@724`, `var nilIfEmpty@725`, `let resolvedImageURL@814`, `func decodedRedditMediaURL@895`, `let decoded@897`, `func decodedThumbnailURL@903`, `func resolveBestRedditImageURL@924`, `let thumbURL@952`, `let components@998`, `let actualItem@999`, `let decodedURLString@1000`, `let actualURL@1001`, `func appendDistinct@1025`, `func imageIdentityKey@1062`
- **Mac only:** `func testImageURLDetection@984`

#### `Podcast/BatchPodcastSession.swift`
- **iOS only:** `var generationBackgroundHandle@34`

#### `Podcast/BatchPodcastView.swift`
- **iOS only:** `var isClear@6`, `struct BatchPodcastFileExporter@445`, `let url@446`, `let onFinish@447`, `func makeCoordinator@449`, `func makeUIViewController@453`, `func updateUIViewController@459`, `class Coordinator@461`, `func documentPicker@468`, `func documentPickerWasCancelled@472`
- **Mac only:** `struct BatchPodcastClearGlassModifier@32`, `func presentSavePanel@448`

#### `Podcast/MLXPodcastPlaybackController.swift`
- **iOS only:** `var interruptionObserver@194`, `var lifecycleObservers@195`, `var idleTimerSettingBeforePreparation@198`, `let activityGate@199`, `func preparePlaybackAudio@433`, `func preparedData@517`, `func configureAudioSession@587`, `func beginPreparationIdleTimerProtection@593`, `func endPreparationIdleTimerProtection@599`, `func pauseForInterruption@664`, `class PodcastApplicationActivityGate@688`, `var active@690`, `var waiters@691`, `func setActive@695`, `func waitUntilActive@704`
- **Mac only:** `func makeSynthesisTask@446`

#### `RSSReaderApp.swift`
- **iOS only:** `class RSSReaderAppDelegate@9`, `func application@10`, `var appDelegate@20`

#### `Services/CloudSyncManager.swift`
- **iOS only:** `func syncLog@15`, `enum FavoriteKind@404`, `struct FavoriteEvent@417`, `let favoriteEventsPerDeviceLimit@423`, `func recordFavorite@428`, `func seedFavoriteRecords@457`, `func effectiveFavorites@474`, `func favoriteIDsWithChangeRecords@490`, `func mergedFavoriteEvents@494`, `func favoriteEvents@505`, `func setFavoriteEvents@513`, `func recordSubscriptionChanges@602`, `func seedSubscriptionRecords@625`, `func effectiveSubscriptions@642`, `func sameSubscriptionContent@684`, `func subscriptionKeysWithRecords@692`, `func hasCloudSubscriptionRecords@696`, `func subscriptionRecords@700`, `func setSubscriptionRecord@716`, `class ReadRecencyStore@1359`, `let lock@1362`, `var firstSeen@1363`, `var isLoaded@1364`, `var pendingSave@1365`, `let entryLimit@1366`, `var fileURL@1368`, `func noteSeen@1373`, `func newest@1393`, `func loadIfNeeded@1406`, `func scheduleSave@1415`, `func save@1424`
- **Mac only:** `var hasCompletedInitialSync@24`, `var isThisDevicePrimary@83`, `var primaryDeviceName@92`, `var hasPrimaryDevice@97`, `func setThisDeviceAsPrimary@102`, `func clearPrimaryDevice@110`, `func syncFavoriteArticles@378`, `func syncFavoriteRedditPosts@411`, `func syncSubscriptions@426`, `func forceSyncSubscriptions@439`, `struct ReadHistoryMigrationResult@974`, `func migrateLegacyReadHistoryToV2@986`

#### `Services/CommentSummaryService.swift`
- **iOS only:** `func extractAllCommentAuthors@125`
- **Mac only:** `func cleanMarkdownArtifactsForDisplay@85`

#### `Services/FeedService.swift`
- **iOS only:** `class CachedArticleContent@158`, `let fullArticleCache@174`, `let fullArticleCacheTTL@180`, `let maxConcurrentFullArticleFetches@181`, `func isAudioMediaURL@532`, `func isImageMediaURL@536`, `func articleContentFingerprint@540`, `func canonicalArticleURL@546`, `func cachedFullArticle@569`, `func cacheFullArticle@590`
- **Mac only:** `let articleAntiBlockTextPhrases@7`, `let articleAdvertisingSelectors@16`, `func containsArticleAntiBlockText@55`, `let normalized@56`, `func stripArticleAdvertisingElements@65`

#### `Services/KokoroTTSService.swift`
- **Mac only:** `func firstReadAloudChunkLength@118`

#### `Services/PersistenceManager.swift`
- **iOS only:** `let cloudKit@9`, `func isOnlyDefaultSubscriptions@245`, `func seedCloudRecordsIfReady@250`, `func mergedFavorites@337`, `func mergedSubscriptions@355`, `func applyCloudKitFavorites@373`, `func applyCloudKitSubscriptions@404`, `func favoriteTombstoneKey@443`, `func tombstones@447`, `func setTombstone@451`
- **Mac only:** `func setThisDeviceAsPrimaryForSubscriptions@651`, `var isThisDevicePrimaryForSubscriptions@660`, `var primaryDeviceNameForSubscriptions@665`, `var hasPrimaryDeviceForSubscriptions@670`, `func backfillReadTokensIfNeeded@798`, `func mergeSubscriptions@981`

#### `Services/PodcastBackgroundTaskManager.swift`
- **iOS only:** `struct PodcastBackgroundSessionLifecycle@7`, `func reset@11`, `func recordRootCompletion@16`, `func recordDependentCompletion@22`, `let logger@34`, `let stateQueue@35`, `let bundleIdentifierPrefix@37`, `let legacyBundleIdentifierPrefix@43`, `var legacyContinuedTaskIdentifier@47`, `var legacyProcessingTaskIdentifier@48`, `var isRegistered@50`, `var activeHandle@51`, `var dependentHandles@52`, `var lifecycle@53`, `var activeContinuedTask@54`, `var activeProcessingTask@55`, `var backgroundObserver@56`, `var foregroundObserver@57`, `var continuedIdentifiers@106`, `var processingIdentifiers@112`, `func registerHandlers@118`, `func registerLifecycleObservers@142`, `func submitContinuedRequest@163`, `func configureContinuedTask@174`, `func configureProcessingTask@204`, `func completeDependent@230`, `func representativeHandleLocked@248`, `func attachSystemProgressToRepresentativeLocked@255`, `func finalizeSessionLocked@264`, `func expireContinuedTask@279`, `func detachActiveSessionLocked@301`, `func handlesSnapshot@326`, `let progress@337`, `let isRootHandle@338`, `let heartbeatInterval@343`, `var lastProgressDate@344`, `var heartbeatTimer@345`, `let stateLock@348`, `var taskProgress@349`, `var finished@352`, `var started@353`, `var requiresSystemSignal@354`, `var startContinuation@355`, `var backgroundTaskIdentifier@356`, `var backgroundReleaseWorkItem@357`, `func startHeartbeat@390`, `func stopHeartbeat@405`, `func heartbeat@413`, `func setRequiresSystemSignal@474`, `func attach@478`, `func notifyTaskStarted@493`, `func notifyCancellation@507`, `func applicationDidEnterBackground@527`, `func applicationWillEnterForeground@531`, `func beginBackgroundAssertion@536`, `func endBackgroundAssertionIfNeeded@560`, `func scheduleBackgroundAssertionReleaseIfNeeded@574`, `extension NSLock@586`, `func withLock@587`
- **Mac only:** `let lock@10`, `var activeHandles@11`, `let activity@35`, `var isFinished@38`, `func cancel@82`

#### `Services/PodcastEpisodeService.swift`
- **iOS only:** `var interruptionObserver@998`, `func configureRemoteCommands@1142`, `func updateNowPlayingInfo@1188`, `func handleInterruption@1200`

#### `Services/RedditOAuthManager.swift`
- **iOS only:** `let scopes@28`, `var scope@29`, `var grantedScopes@41`, `func clearStoredTokens@449`, `var hasReplyPermission@463`, `func hasReplyPermission@467`
- **Mac only:** `let scope@29`, `var pendingAuthState@53`, `var pendingAuthCompletion@54`, `func handleMacOSCallback@208`

#### `Services/RedditService.swift`
- **iOS only:** `let error@6`, `let httpStatusCode@7`, `let wasCacheHit@8`, `let rateLimitRemaining@9`, `let rateLimitReset@10`, `let retryAfter@11`, `case invalidResponse@41`, `case httpError@42`, `case parsingFailed@43`, `func userFacingHTTPMessage@62`, `var statusCode@91`, `var rateLimitReset@98`, `var retryAfter@105`, `let commentSession@147`, `func commentOnPost@660`, `func submittedComment@679`, `func invalidateCommentCache@846`, `func decodeCommentsResponse@972`, `func extractRateLimitInfo@1001`, `func formatCooldownDuration@1023`, `func buildCooldownMessage@1036`
- **Mac only:** `struct RedditRateLimitStatus@4`, `enum Endpoint@5`, `let statusCode@10`, `let message@11`, `let remaining@12`, `let resetInterval@13`, `let used@14`, `let endpoint@16`, `let capturedAt@17`, `var isRateLimited@19`, `var approximateResetDate@23`, `let rateLimit@31`, `let fromCache@32`, `let errorDescription@33`, `var error@35`, `case httpStatus@72`, `case decoding@73`, `case transport@74`, `func cachedSubredditIcon@118`, `func storeSubredditIcon@123`, `var feedRateLimitStatus@131`, `var commentRateLimitStatus@132`, `let rateLimitQueue@133`, `func reserveRateLimitSlot@182`, `func captureRateLimit@200`, `func parseHeaderDouble@250`, `func storeRateLimit@260`, `func latestFeedRateLimitStatus@274`, `func latestCommentRateLimitStatus@280`, `func clearFeedRateLimitStatus@289`, `func suggestedDelay@295`, `func cleanedIconURL@355`

#### `Services/SummarizeBridge.swift`
- **iOS only:** `case missingHost@150`, `case missingToken@151`, `let openAICompatibleAPIKeyKey@179`, `func decodeErrorBody@528`, `struct ChatCompletionRequest@540`, `struct ChatMessage@546`, `struct ChatCompletionResponse@551`, `struct Choice@570`, `struct ErrorBody@574`, `var timeoutWorkItem@612`, `func installTimeoutWorkItem@621`
- **Mac only:** `case fmNotFound@151`, `case processFailed@152`, `case terminalAutomationFailed@153`, `case cancelled@155`, `func nonInteractiveAuthenticationContext@189`, `let fmURL@465`, `let ansiPattern@466`, `let helperDirectory@467`, `let processQueue@471`, `var currentProcess@472`, `var currentTerminalShellPID@473`, `func availabilityDescription@481`, `func cancel@537`, `func runFM@557`, `func setCurrentProcess@596`, `func clearCurrentProcess@602`, `func setCurrentTerminalShellPID@610`, `func runFMViaTerminalHelper@616`, `func ensureTerminalHelperStarted@672`, `func runOneShotViaTerminal@736`, `func runProcess@786`, `func stripANSI@801`, `func isPCCContextUnavailable@811`, `func cleanFMResponse@818`, `func terminateTerminalJob@826`, `func runDetachedProcess@832`, `func readPID@839`, `func isProcessRunning@844`, `func shellDisplayArgument@857`, `class LockedProcessOutput@865`, `var data@867`, `func stringValue@875`, `func run@911`

#### `Services/SummaryService.swift`
- **iOS only:** `var errorDescription@15`, `var localTTSEngine@54`, `var kokoroVoice@55`, `var kokoroSpeed@56`, `var kokoroPrecacheEnabled@57`, `func summarizeTextAsync@454`, `func requestGeminiContent@589`, `func performGeminiSummary@697`, `class SoundDelegate@1821`, `var onPlaybackFinished@1822`, `var onSpeechFinished@1823`, `func audioPlayerDidFinishPlaying@1825`, `func speechSynthesizer@1828`, `func sound@1837`, `func createWavData@1847`, `var header@1848`, `let pcmDataSize@1849`, `var chunkSize@1850`, `var subChunk1Size@1851`, `var audioFormat@1852`, `var mutableChannels@1863`, `var mutableSampleRate@1865`, `let byteRate@1867`, `var mutableByteRate@1868`, `let blockAlign@1870`, `var mutableBlockAlign@1871`, `var mutableBits@1873`, `var mutablePcmSize@1878`, `var out@1881`, `func isMP3Data@1887`, `let bytes@1889`, `let sync@1891`, `func isAACData@1896`, `func setMacSpeechVoice@1905`, `func availableMacVoices@1909`, `func preferredMacVoiceIdentifier@1917`, `let available@1918`, `struct VoiceInfo@1920`, `let voiceInfos@1926`, `func scoreVoice@1936`, `func ensureIOSOnMacPinnedVoice@1970`, `extension ShortcutsTTS@2026`, `func speakUsingXCallbackOniOS@2028`, `func speakUsingShortcutsCLI@2097`, `func launchShortcutViaURLSchemeForMac@2162`, `func withAIBackgroundTask@2234`, `let handle@2240`
- **Mac only:** `case invalidResponse@14`, `case apiError@15`, `case noContent@16`, `struct CLIJob@1590`, `let cliQueue@1594`, `var activeJobs@1595`, `func speakViaURLScheme@1633`, `func speakViaCLI@1684`

#### `Utilities/AudioUtils.swift`
- **iOS only:** `func configureAudioSessionForTTSPlayback@84`, `let audioSession@85`, `let available@106`
- **Mac only:** `func isAACData@83`, `extension NSSpeechSynthesizer.VoiceName@92`, `let availableNames@99`, `func setMacSpeechVoice@342`

#### `Views/AIQuestionView.swift`
- **iOS only:** `var articleContent@5`, `var appState@7`, `func submitQuestion@122`
- **Mac only:** `func askQuestion@106`

#### `Views/CommentViews.swift`
- **iOS only:** `let onReplyPosted@103`, `var avatarSide@135`, `let title@543`, `let contextSystemImage@544`, `let contextTitle@545`, `let contextBody@546`, `let placeholder@547`, `var darkReplyComposer@585`, `var darkHeader@661`, `var parentCommentPreview@724`, `var lightReplyComposer@752`
- **Mac only:** `var isRunningIOSOnMac@32`, `func extractNonImageLinks@180`, `func formatCommentBodyBlocks@282`, `func commentBodyText@483`, `var actionsFitOnHeaderLine@639`, `var collapseButton@641`, `var trimmedReply@761`, `var lavender@769`, `var panelBackground@773`, `var darkReplyView@794`, `var lightReplyView@935`

#### `Views/ContentView.swift`
- **iOS only:** `let articleAntiBlockPhrases@7`, `let articleAntiBlockAdSelectors@16`, `let articleAntiBlockAdSelectorString@45`, `func javaScriptStringLiteral@58`, `var escaped@59`, `func articleAntiBlockCheckJavaScript@73`, `let phrases@74`, `func is9to5MacArticleURL@87`, `func articleAntiBlockCleanupJavaScript@92`, `let selectors@94`, `struct PodcastCompletionNoticeSurface@187`, `extension Notification.Name@205`, `let articleReaderScrollToTopRequested@206`, `let readerColumnMaxWidth@215`, `let readerColumnSidePadding@216`, `let audioSession@677`, `var isDetailActive@1177`, `func setPlatformClipboardString@1478`, `struct ArticleDetailScrollOffsetPreferenceKey@1531`, `var defaultValue@1532`, `func reduce@1534`, `func anywhereSwipeBack@1613`, `struct TrackpadScrollGestureOverlay@1685`, `var isEnabled@1686`, `let onSwipeRight@1687`, `class TrackpadGestureView@1701`, `var onSwipeRight@1702`, `var isBackSwipeEnabled@1703`, `var accumulatedX@1704`, `var accumulatedY@1705`, `var lastBackSwipeTime@1709`, `func setup@1737`, `func didMoveToWindow@1745`, `func handleTrackpadPan@1770`, `func gestureRecognizerShouldBegin@1815`, `func gestureRecognizer@1823`, `struct NativeScrollGeometry@1882`, `class NativeScrollRestorationTracker@1888`, `struct NativeScrollRestorationModifier@1896`, `let scrollToTopRequest@1903`, `let onRawScrollActivity@1904`, `extension UIView@2096`, `class ArticleScrollToTopController@2111`, `func registerOuterScrollView@2117`, `func registerReaderWebView@2121`, `func performScrollToTop@2137`, `func topContentOffset@2154`, `func scrollWebViewToTop@2158`, `func visibleScrollViews@2187`, `func collectScrollViews@2196`, `struct ArticleOuterScrollViewResolver@2209`, `struct IOSArticleActionCapsule@2226`, `struct ArticleActionSeparator@2264`, `struct IOSArticleChromeIconButtonStyle@2274`, `struct IOSArticleChromeLabeledButtonStyle@2293`, `struct IOSArticleChromeSelectedButtonStyle@2312`, `struct DetailTopBar@2334`, `let articleViewMode@2338`, `var selectedArticleHasReaderURL@2469`, `func toggleArticleViewMode@2475`, `func articleModeToggleLabel@2483`, `var summarizeLabel@2497`, `func topBarIcon@2510`, `var controlFill@2711`, `var selectedFill@2722`, `struct RedditSummaryScopeGlassModifier@2800`, `let shape@2801`, `let isInteractive@2803`, `func redditSummaryScopeGlass@2844`, `struct RedditFloatingSubscriptionChrome@2859`, `let statusMessage@2860`, `let hidesSortBar@2861`, `var sortOption@2862`, `let onSortChange@2863`, `var contentWindowWidth@2976`, `var feedRowsUsePhoneLayout@2979`, `var isPhoneStyleLayout@2984`, `var cachedShouldUsePhoneLayout@2990`, `var phoneLibraryCategory@3000`, `var redditSubscriptionScrollOffset@3006`, `var subscriptionScrollToTopRequests@3007`, `var isRedditSubscriptionSortBarHidden@3008`, `var redditSubscriptionScrollIdleTask@3009`, `var lastPhoneSidebarSubscriptionURL@3011`, `var phoneSidebarRestoreTask@3012`, `var isBackSwipeInProgress@3015`, `var iPadShellBackground@3030`, `func isPodcastSubscription@3066`, `func noteRedditSubscriptionScrollActivity@3078`, `var shouldHideRedditSubscriptionSortBar@3100`, `var shouldShowRedditSubscriptionToolbarSortMenu@3110`, `func restorePhoneSidebarPosition@3119`, `func ipadListWidth@3154`, `let ipadMinimumReaderWidth@3160`, `func ipadReaderIsTooNarrow@3162`, `func withReadingPane@3169`, `func libraryLink@3987`, `func sidebarUnreadCount@4468`, `struct CompactSummaryReliabilitySheet@5690`, `let message@5693`, `let onGenerateSummary@5694`, `let onContinue@5695`, `var qaAnswerMarkdownText@5754`, `var isAskingSelectionAI@5758`, `var selectionAskAIPrompt@5759`, `var showSelectionAskAISheet@5763`, `var qaSelectionOrigin@5764`, `var baseSummaryClipboardText@5765`, `var cachedSummaryClipboardText@5766`, `var cachedFormattedAggregateSummary@5767`, `var parsedSummaryDisplayCache@5769`, `var summaryChromeHeight@5780`, `var summaryChromeReturnTask@5781`, `let reliabilityWarningMessage@5788`, `var compactReliabilityWarningBinding@5791`, `var regularReliabilityWarningBinding@5798`, `var isWhiteboardMinimized@5811`, `var isInfographicMinimized@5818`, `func formatOverallSummaryForDisplay@5829`, `func rebuildAggregateSummaryCache@5869`, `func summaryDisplayCacheKey@5883`, `func scrollToOverallSummary@5940`, `var formattedAggregateSummary@6044`, `var reliabilityWarningActions@6138`, `func summaryCard@6151`, `func scheduleSummaryChromeReturn@7003`, `func sourceContextForGlobalSelection@7152`, `func handleSummaryAskAISelection@7156`, `func handleSummaryAskAIWebSelection@7201`, `func handleSummaryAnswerSelection@7245`, `func buildWhiteboardPrompt@7304`, `func buildWhiteboardWebPrompt@7350`, `func generateWhiteboardWithAppleLocal@7536`, `func generateWhiteboardWithChatGPT@7658`, `func generateWhiteboardWithOpenAICompatible@7690`, `func runAppleCloudStructured@7754`, `func appleCloudTimeoutSeconds@7800`, `actor AppleCloudShortcutCallbackBox@7807`, `func setResult@7811`, `func setError@7812`, `func snapshot@7813`, `func waitForAppleCloudOutput@7816`, `func satisfiesRequiredKeys@7843`, `func isValidJSONCandidate@7854`, `func currentClipboardString@7934`, `struct AppleCloudIncompleteStructuredOutput@7968`, `func isAppleCloudWhiteboardJSONSufficient@7973`, `func isAppleCloudInfographicJSONSufficient@7988`, `func regenerateAppleCloudStructuredJSON@8008`, `func handleWhiteboardResponse@8243`, `func repairInvalidJSON@8272`, `func repairInvalidJSONFromMLX@8394`, `func buildInfographicPrompt@9269`, `func buildInfographicWebPrompt@9313`, `struct MinimizedFloatingPill@10376`, `let color@10379`, `let onRestore@10380`, `var isExpanded@10383`, `let htmlData@10441`, `let onDismiss@10442`, `var onMinimize@10443`, `var webViewRef@10447`, `var askAIPrompt@10449`, `var askAIMarkdownResponse@10451`, `var showAskAIResponseSheet@10452`, `func copyWhiteboardImage@10536`, `func copyAskAIResponseToClipboard@10581`, `var onAskAISelection@10599`, `var onAskAIWebSelection@10600`, `var imageAspectRatio@11039`, `let maximumFillCropFactor@11043`, `var fillsBoxDespiteBackdrop@11045`, `func thumbnail@11085`, `var placeholder@11105`, `var feedRowUsesPhoneLayout@11150`, `var isOpen@11154`, `var showsSource@11156`, `var usesFlatIpadRow@11158`, `var usesExpandedIpadThumbnail@11162`, `var usesExpandedPhoneThumbnail@11170`, `var articleThumbnailWidth@11174`, `var articleThumbnailHeight@11180`, `var articleMetadataFontSize@11186`, `var articleCardTitleText@11196`, `func articleCardPreviewText@11206`, `var ipadArticlePreviewText@11218`, `var cardBackground@11224`, `var cardBorderColor@11228`, `var phoneRow@11243`, `var cardRow@11326`, `var expandedIpadArticleContent@11456`, `var compactIOSArticleContent@11491`, `func formatDate@11538`, `let todayTimeFormatter@11556`, `let weekdayFormatter@11562`, `let compactDateFormatter@11568`, `enum SplitViewSidebarToggle@11579`, `func toggle@11581`, `func show@11594`, `func hide@11604`, `func findSplit@11613`, `struct FeedRowUsesPhoneLayoutKey@11626`, `extension EnvironmentValues@11636`, `enum FeedRowStyle@11646`, `func usesFlatRows@11647`, `func flatRowBackground@11655`, `var flatRowDivider@11660`, `var usesExpandedIOSSubscriptionLayout@11704`, `var redditThumbnailWidth@11708`, `var redditThumbnailHeight@11714`, `var redditThumbnailContentMode@11720`, `var previewLineLimit@11724`, `var compactThumbnailHeight@11729`, `var inlineScore@11733`, `var cardPreviewText@11746`, `var cardTitleText@11754`, `var regularCardContent@11803`, `var phoneCardContent@11933`, `var isPreparingLocalTTSQA@12026`, `func isFullBleedIpadReader@12146`, `func articleOuterHorizontalPadding@12158`, `func articleDetailBackground@12288`, `func noteArticleReaderScrollActivity@12359`, `func hideArticleReadingChromeTemporarily@12379`, `func linkifiedPlainText@12634`, `func isArticleSummaryVisible@12827`, `var articleLanguageChip@12974`, `func articleMetadataPanelBackground@13030`, `func articleSummaryToolbarClearance@13062`, `func qaActionRow@13191`, `func podcastTimestampTapHandler@13284`, `func runSelectionAskAI@13433`, `var readerLoadingFallback@14345`, `func hideForRSSFallback@15160`, `func evaluateReaderMode@15312`, `func verifyAntiBlockAfterReader@15352`, `class ReaderDOMReadyMessageProxy@15403`, `var usesFullWidthReader@15480`, `struct MarkAllReadMenu@16023`, `let category@16025`, `var isConfirming@16026`, `var confirmCount@16027`, `var rowWidth@16028`, `var itemName@16030`, `var appearanceMode@16096`, `var preferredScheme@16098`, `var effectiveScheme@16106`, `var sourceOptions@16108`, `var sourceOptionsWithoutIcons@16122`, `var sourceSectionTitle@16288`, `struct PhoneSummaryToolbarButtonStyle@16359`, `struct PhoneSummaryToolbarButton@16364`, `struct SummaryToolbarLayoutModifier@16377`, `let compact@16378`, `var glassTint@16484`, `var isSpeaking@16490`, `var borderOverlay@16749`, `var backgroundFillColor@16773`, `let markdownText@16786`, `let displaySummary@16787`, `var summaryReferenceCount@16790`, `var onSummaryReferenceTap@16791`, `var onPodcastTimestampTap@16792`, `var throughputText@16907`, `struct ArticleGlassySummaryContent@17306`, `let onAskAISelection@17310`, `let onAskAIWebSelection@17311`, `let summaryReferenceCount@17312`, `let onSummaryReferenceTap@17313`, `let onPodcastTimestampTap@17314`, `let headerTitle@17316`, `let isSynthesizingSpeech@17318`, `let isSpeakingLocally@17319`, `let isPreparingLocalTTS@17320`, `let speechSynthesisError@17321`, `let throughputText@17322`, `let speakSummary@17323`, `let stopArticleSummarySpeech@17324`, `let speakSummaryLocally@17325`, `struct EdgeBackSwipeRecognizer@17634`, `func handleEdgePan@17657`, `func edgeSwipeBack@17706`, `func fullScreenEdgeBackSwipe@17734`, `func systemEdgeBackSwipe@17757`, `func phoneStyleBackGestures@17781`
- **Mac only:** `let articleReaderAntiBlockPhrases@12`, `func articleReaderJavaScriptArrayLiteral@23`, `let data@25`, `let literal@26`, `func articleReaderAntiBlockCheckScript@43`, `let phrasesLiteral@44`, `func performTrackpadBackNavigation@790`, `func performForwardNavigation@796`, `func handleBackKeyPress@803`, `func handleForwardKeyPress@813`, `struct MacNavigationSwipeView@823`, `let onBack@824`, `let onForward@825`, `class SwipeCaptureView@839`, `func configure@858`, `func hitTest@864`, `func viewDidMoveToWindow@869`, `func viewWillMove@874`, `func viewDidMoveToSuperview@881`, `func refreshEventMonitor@892`, `func removeEventMonitor@901`, `func handleScroll@908`, `func rgb@1175`, `func macDynamicColor@1179`, `func copyToClipboard@1193`, `func copyURLToClipboard@1202`, `let macArticleScrollMessageName@1222`, `let macArticleContentHeightMessageName@1223`, `let macArticleScrollReporterScript@1225`, `let macArticleContentHeightReporterScript@1257`, `func firstDescendantScrollView@1318`, `func firstAncestorScrollView@1332`, `var current@1333`, `func firstAncestorWebView@1344`, `func normalizedMacScrollOffset@1356`, `let rawOffset@1377`, `let insetAdjustedOffset@1378`, `struct MacNativeScrollGeometry@1424`, `class MacNativeScrollRestorationTracker@1430`, `struct MacNativeScrollRestorationModifier@1438`, `let macArticleMetadataTopRevealPadding@1587`, `struct MacArticleScrollGestureMonitor@1589`, `let onScrollOffsetChange@1591`, `class MonitorView@1606`, `func reportWebScrollOffsetAfterScrollingSettles@1684`, `struct MacArticleScrollActivityObserver@1716`, `class ObserverView@1730`, `func attachToEnclosingScrollViewIfNeeded@1747`, `func scheduleAttachRetryIfNeeded@1771`, `func handleLiveScroll@1783`, `var selectedFillColor@2118`, `var selectedTextColor@2124`, `var idleTextColor@2128`, `struct MacRedditSummaryScopeButtonGlassModifier@2136`, `func macRedditSummaryScopeButtonGlass@2154`, `var macReaderPaneWidth@2248`, `func articleHasVisibleAIBox@2548`, `var redditFloatingChromeTopPadding@3644`, `func redditFloatingContentTopInset@3655`, `func redditFloatingSortChrome@3660`, `func summarizeFeedButton@4038`, `func feedScrollToTopButton@4053`, `func feedMarkAllButton@4070`, `func summarizeRedditButton@4086`, `func redditScrollToTopButton@4217`, `func redditMarkAllButton@4238`, `var macArticlePillTrailingInset@4290`, `var showsMacTodayOverview@4295`, `var macTodayOverview@4304`, `var macReaderColumn@4365`, `func clearContentSelection@4407`, `extension ContentView@4416`, `func sidebarList@4418`, `func sidebarLibraryLink@4450`, `func feedSection@4470`, `func subscriptionsSection@4605`, `func sidebarSettingsSection@4630`, `func subscriptionRowContent@4663`, `struct RedditRateLimitBanner@4685`, `let status@4686`, `struct MacArticleActionCapsule@4807`, `struct MacArticleChromeIconButtonStyle@4829`, `var isActive@4830`, `struct MacArticleChromeLabeledButtonStyle@4850`, `struct MacSummaryActionCapsule@4867`, `struct MacSummaryActionPillModifier@4883`, `struct MacSummaryActionLabeledButtonStyle@4913`, `struct MacSummaryActionIconButtonStyle@4927`, `var didFail@5140`, `func reliableImage@5187`, `struct FeedListRow@5237`, `let snippet@5239`, `let imageURL@5240`, `let isUnread@5241`, `let meta@5243`, `let footer@5244`, `let thumbnailSize@5246`, `enum TodayOverviewFormatter@5312`, `struct Formatted@5313`, `func format@5318`, `func linkifiedDescription@5345`, `var attributed@5346`, `let nsText@5350`, `func feedRowTimestamp@5361`, `let calendar@5362`, `var showsPublicationSource@5375`, `var titleText@5381`, `var snippetText@5391`, `var showSelectionAskAIResponse@5517`, `var isSelectionAskAIInFlight@5518`, `var selectionAskAIError@5521`, `var selectionAskAITask@5522`, `var macArticleScrollOffset@5544`, `var macArticleMetadataRevealWorkItem@5545`, `var articleTopOverlayMetadataOffset@5645`, `var articleReaderTopContentInset@5653`, `var articleReaderChromeHeightEstimate@5661`, `var macArticleTopGlassEdge@5713`, `var articleDetailBackground@5840`, `var macArticleMetadataTopRevealThreshold@5949`, `func handleMacOuterArticleScrollOffsetChange@5957`, `func handleMacArticleContentScrollOffsetChange@5966`, `func updateMacArticleChromeForScrollOffset@5970`, `func scheduleMacArticleMetadataRevealIfStillAtTop@5984`, `func narrowPaneTopClearance@6318`, `func articleMetadataItem@6550`, `func articleMetadataDivider@6573`, `func normalizedArticleAuthor@6580`, `func youtubeTimestampTapHandler@6796`, `func askAIFromArticleSelection@6924`, `func copySelectionAskAIResponse@6982`, `let articleTitle@7761`, `let feedTitle@7762`, `let onMacArticleScrollOffsetChange@7771`, `var readerContentHeight@7781`, `var canShowReaderMode@7803`, `var articleModeControl@7839`, `func articleModeButton@7870`, `func readerLoadingFallback@8008`, `func stripHighRiskAdMarkup@8579`, `struct DelayedReaderReveal@9054`, `let delay@9055`, `var isVisible@9057`, `class MacReaderDOMReadyMessageProxy@9074`, `class MacArticleReaderWKWebView@9084`, `var forwardsVerticalScrollingToAncestor@9085`, `func scrollWheel@9087`, `let forwardsScrollingToAncestor@9108`, `func applyDocumentTopInset@9143`, `func installWebPageChromeSuppression@9172`, `func attachScrollObserver@9350`, `func applyScrollingMode@9429`, `func scheduleContentHeightMeasurements@9451`, `func measureContentHeight@9461`, `func scheduleTopContentInsetRetry@9481`, `func removeScrollObserver@9493`, `func scheduleScrollOffsetSettlingReports@9518`, `func handleScrollBoundsDidChange@9529`, `func handleLiveScrollEnded@9537`, `func reportScrollOffset@9541`, `func normalizedScrollOffset@9551`, `func normalizedReaderScrollOffset@9559`, `func reportScriptScrollOffset@9575`, `func reportJavaScriptScrollOffset@9579`, `func publishContentHeight@9618`, `func detectAntiBlockMessage@9736`, `func handleAntiBlockDetected@9748`, `var type@10452`, `var iosBody@10471`, `var urlEntryField@10519`, `var macBody@10532`, `var iosAddSheetBackground@10689`, `var isHovered@10932`, `let isHovered@10952`, `var markdownText@11071`, `var podcastPlayer@11073`, `var onAskAI@11074`, `var onAskAIWeb@11075`, `var onTimestampTap@11077`, `func startKokoroPlaybackSummary@11685`, `struct SidebarSubscriptionGlassModifier@11976`, `func sidebarSubscriptionGlass@11996`, `struct MacListSelectionClearView@12002`, `struct MacWindowChromeBackgroundView@12029`, `let isDark@12030`, `func apply@12046`, `func makeToolbarChromeMoreTranslucent@12061`, `func softenVisualEffects@12066`, `extension NSView@12080`, `func firstDescendant@12092`, `let summaryAnswerGlassTint@12272`, `struct SummaryAnswerGlassSurfaceModifier@12274`, `func summaryAnswerGlassSurface@12308`, `struct MacSummaryAnswerSheetContent@12313`, `let answer@12314`, `struct SummaryScrollMetrics@12380`, `var summaryChromeRevealTask@12410`, `var summaryScrollMetrics@12416`, `var isOverallSummaryVisible@12420`, `var snapshotAggregateSummaryText@12421`, `let panelWidth@12425`, `let summaryHorizontalInset@12426`, `var isSynthesizingSpeechDrag@12442`, `var isPreparingLocalTTSDrag@12443`, `var isSpeakingLocallyDrag@12444`, `var speechSynthesisErrorDrag@12445`, `var audioPlayerDrag@12446`, `var soundDelegateDrag@12447`, `var nextAudioChunkDrag@12448`, `var ttsCanceledDrag@12449`, `var localTTSTaskDrag@12450`, `func returnToSummaryOrigin@12518`, `func restoreSummaryScrollPositionAfterRefresh@12585`, `var askAIHandler@12608`, `var askAIWebHandler@12614`, `var summaryToolbar@12620`, `func visualSummaryContent@13464`, `func visualURLReferenceList@13472`, `func whiteboardPromptForWebAI@13494`, `func infographicPromptForWebAI@13503`, `func buildAskAIContext@13637`, `func makeAskAISelectionPrompt@13659`, `func performAskAI@13679`, `func askAIResponse@13724`, `func askAIFromSummarySelection@13740`, `func generateInfographicWithGemini@14640`, `func generateInfographicWithSummarize@14688`, `func generateInfographicWithPCCGateway@14726`, `func generateInfographicWithMLXLocal@14805`, `func parseInfographicPayload@14898`, `func buildDragSpeechText@15639`, `func speakDragOverviewCloudTTS@15648`, `func stopDragOverviewSpeech@15692`, `func playDragAudio@15705`, `func speakDragOverviewLocally@15728`, `func startKokoroPlaybackDrag@15801`, `var showAskAIResponse@16276`, `var askAIError@16279`, `func copyAskAIResponse@16381`, `func installEditMenuInteraction@16491`, `func editMenuInteraction@16499`, `func sendSelection@16517`, `struct GlobalSummaryResultView@16629`, `var parsedResult@16649`, `func buildSpeechText@16969`, `func speakOverviewCloudTTS@16978`, `func stopOverviewSpeech@17023`, `func speakOverviewLocally@17060`, `func startKokoroPlaybackOverview@17134`

#### `Views/InfographicView.swift`
- **iOS only:** `var onMinimize@13`, `var appState@14`, `var askAIPrompt@24`, `var askAIMarkdownResponse@26`, `var showAskAIResponseSheet@27`, `func copyAskAIResponseToClipboard@316`, `var onAskAISelection@332`, `var onAskAIWebSelection@333`
- **Mac only:** `var onAskAI@15`, `var onAskAIWeb@16`, `var showAskAIResponse@25`, `var askAIError@28`, `var infographicContent@63`, `func copyAskAIResponse@216`, `func installEditMenuInteraction@456`, `func editMenuInteraction@464`, `func sendSelection@482`

#### `Views/MainSplitView.swift`
- **Mac only:** `extension MainSplitView@37`, `var settingsButton@38`, `var settingsSheetContent@47`, `var sortedArticles@98`

#### `Views/PlatformViews.swift`
- **Mac only:** `struct AdaptiveGlassModifier@233`, `func body@242`

#### `Views/PodcastEpisodePlayerView.swift`
- **Mac only:** `struct PodcastTimestampCitationView@348`, `let text@349`, `var linkedText@366`, `func seconds@392`

#### `Views/RedditDetailView.swift`
- **iOS only:** `func ensureBackgroundTTSReady@8`, `let audioSession@9`, `struct RedditCommentsChromeIconButtonStyle@97`, `var horizontalSizeClass@139`, `var commentLoadStatusMessage@145`, `var postCommentTarget@146`, `let redditQAAnchor@167`, `var iphoneDetailHorizontalInset@168`, `var detailBackground@170`, `var shouldShowMaterialOverlay@174`, `var postTitleFont@178`, `var isAskingSelectionAI@236`, `var selectionAskAIPrompt@237`, `var showSelectionAskAISheet@241`, `var selectedMacVoiceID@270`, `var isCompactWidth@363`, `func usesCompactDetailLayout@367`, `func detailContentWidth@373`, `func detailTopPadding@379`, `var usesExpandedIpadDetailImage@387`, `var usesExpandedPhoneDetailImage@395`, `func mainImageWidth@403`, `func scrollToRedditQAIfNeeded@421`, `var redditQAAccentColor@1246`, `func redditQASection@1250`, `func closeRedditQA@1290`, `func redditQAAnswerContent@1300`, `func redditQAUtilityButtons@1336`, `func redditQAStatusIndicators@1374`, `func regularCommentsSectionHeader@1474`, `func compactCommentsSectionHeader@1484`, `func compactCommentsHeaderActions@1498`, `var compactAddCommentButton@1540`, `func postCommentSheet@1817`, `func handleTopLevelCommentPosted@1835`, `func handleReplyPosted@1855`, `func commentsByAppendingReply@1878`, `func containsComment@1923`, `func requestWebCommentSummary@2313`, `func handleAskAISelection@2422`, `func handleAskAIWebSelection@2426`, `func handleQAAskAISelection@2430`, `func handleQAAskAIWebSelection@2447`, `func runSelectionAskAI@2464`, `func isLocalAnalysisError@3777`, `func prepareForRoutedThematicAnalysis@3785`, `struct AdaptiveGlassModifier@4020`, `let cornerRadius@4021`, `let tintColor@4022`, `var onAskAISelection@4055`, `var onAskAIWebSelection@4056`, `var displaySummaryText@4078`, `var displaySummary@4657`, `struct OverlayBarScrollEdgeFade@5271`, `let bottomToolbarClearance@5273`, `let bottomFadeHeight@5274`, `let height@5276`
- **Mac only:** `struct RedditCommentsActionPillModifier@65`, `struct RedditQAActionButtonStyle@124`, `var commentBanner@155`, `var commentLoadError@156`, `var commentLoadTask@157`, `var redditPaneWidth@164`, `let toolbarPlacement@169`, `var qaAnswerButtonSpacing@219`, `var answerParagraphs@231`, `var showSelectionAskAIResponse@233`, `var isSelectionAskAIInFlight@234`, `var selectionAskAIError@237`, `var selectionAskAITask@238`, `var isSynthesizingSpeechSummary@262`, `var isPreparingLocalTTSSummary@263`, `var isSpeakingLocallySummary@264`, `var speechSynthesisErrorSummary@265`, `var ttsCanceledSummary@266`, `var audioPlayerSummary@268`, `var localSpeechSynthSummary@269`, `var soundDelegateSummary@270`, `var nextAudioChunkSummary@271`, `var localTTSTaskSummary@272`, `var formattedAnswerText@292`, `func distinctAdditionalImages@431`, `func imageKey@432`, `func redditSingleColumn@439`, `func redditPostMainContent@471`, `func redditCommentsContent@793`, `func openPostLink@1296`, `func applyCommentResult@1581`, `func buildRateLimitMessage@1627`, `func summarizePost@1935`, `func shouldAcceptCommentSummaryResult@1941`, `func askAIFromRedditQASelection@2028`, `func askAIFromRedditSelection@2050`, `func copySelectionAskAIResponse@2109`, `func decodeParagraphArray@2120`, `func cleanedParagraphs@2142`, `func speakPostSummary@2952`, `func stopPostSummarySpeech@3014`, `func playAudioSummary@3032`, `func speakPostSummaryLocally@3101`, `func startKokoroPlaybackRedditQA@3325`, `func startKokoroPlaybackRedditSummary@3470`, `var onAskAI@4323`, `var onAskAIWeb@4324`, `var didCopy@4326`, `func startKokoroPlaybackGlassy@4892`

#### `Views/SettingsView.swift`
- **iOS only:** `let settingsGlassTint@13`, `struct SettingsCapsuleButtonStyle@16`, `var prominent@17`, `struct SettingsPillPicker@45`, `struct Option@46`, `let options@52`, `var selection@53`, `var fillsWidth@56`, `var compact@58`, `var pills@71`, `struct EqualWidthPillRow@103`, `var spacing@104`, `var compresses@106`, `func widestIdeal@108`, `func sizeThatFits@112`, `func placeSubviews@122`, `enum SettingsLayout@138`, `var isPhone@139`, `struct SettingsPillSurface@148`, `enum SettingsPalette@166`, `func background@167`, `func panelFill@174`, `struct SettingsTextFieldSurface@182`, `func settingsTextField@202`, `struct SettingsFormWidthPreferenceKey@207`, `var defaultValue@208`, `func reduce@210`, `struct RSSSettingsPresentationBackground@216`, `var horizontalSizeClass@251`, `var settingsFormWidth@303`, `var usesCompactSettingsLayout@306`, `var settingsPanelFill@368`, `func refreshChatGPTWebAILoginState@396`, `func refreshGeminiWebAILoginState@412`, `var redditAuthenticatedRegularView@1482`, `var redditAuthenticatedPhoneView@1522`, `var redditAuthButtons@1554`, `var refreshRedditTokenButton@1562`, `var reconnectRedditButton@1572`, `var logoutRedditButton@1583`, `func reconnectReddit@1614`, `func refreshRedditToken@1619`, `func signInWithReddit@1630`
- **Mac only:** `let macSettingsGlassTint@11`, `struct MacSettingsGlassButtonStyle@14`, `let prominent@15`, `let tintColor@16`, `struct MacSettingsSelectorSurface@35`, `struct MacSettingsSelectorButtonStyle@71`, `func settingsGlassControlGroup@85`, `func settingsGlassIconButtonStyle@98`, `func settingsGlassButtonStyle@114`, `func settingsGlassPanel@133`, `var isMigratingReadHistory@163`, `var deleteLegacyReadHistoryAfterMigration@164`, `var showReadHistoryMigrationConfirm@165`, `func refreshWebAILoginStates@280`, `func summaryProviderDidChange@308`, `var macAppearanceSelector@323`, `func macSummaryProviderTitle@334`, `var macSummaryProviderSelector@344`, `var macWebAISessionButtons@362`, `var macWebAISelector@392`, `func settingsNavigationContainer@1358`, `func startReadHistoryMigration@1439`

#### `Views/SummaryColumnView.swift`
- **iOS only:** `func ensureBackgroundTTSReady@6`, `let audioSession@7`, `var isAskingSelectionAI@38`, `var selectionAskAIPrompt@39`, `var showSelectionAskAISheet@43`, `func handleAskAISelection@757`, `func handleAskAIWebSelection@761`, `func runSelectionAskAI@765`
- **Mac only:** `var showSelectionAskAIResponse@45`, `var isSelectionAskAIInFlight@46`, `var selectionAskAIError@49`, `var selectionAskAITask@50`, `func startKokoroPlayback@709`, `func askAIFromSummaryColumnSelection@875`, `func copySelectionAskAIResponse@925`

#### `Views/WebAIHandoffView.swift`
- **iOS only:** `func keepWebViewsAwake@20`, `func cancelActiveRequest@100`, `struct WebAIHandoffRestoreGlassModifier@324`
- **Mac only:** `var colorScheme@667`, `func strippingProviderBanners@1551`

#### `Views/YouTubePlayerView.swift`
- **Mac only:** `class YouTubeScrollForwardingWebView@112`, `func scrollWheel@113`, `func makeNSView@134`, `func updateNSView@147`, `func dismantleNSView@159`


