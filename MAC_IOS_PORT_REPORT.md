# Mac iOS-feature port — 7 October 2026

Applied only to `/Volumes/screen/rss mac copy`. The iOS reference at `/Volumes/screen/rss latest ios27 - UI fix copy` was read only. All 68 initially captured Swift/project/plist/entitlement reference files still match their SHA-256 hashes.

The existing Mac working tree was preserved in `/private/tmp/rss-mac-ios-port-baseline` before edits. That snapshot is a temporary local source backup, not a Git commit. At source-port completion, no app build, install, launch, push, signing, CloudKit schema deployment, or external account operation had been performed. The subsequently requested development build and launch are recorded below.

## Features applied

- **Sync:** CKSyncEngine private database sync; read records; timestamped favorites/subscriptions and removal records; local tombstones; legacy KVS compatibility; recency-aware quota cleanup; default-only subscription upload protection; coalesced CloudKit/poll UI updates with Mac unread-cache rebuilds. Primary-device and manual read-history migration controls were removed. Mac sync state stays under its own application-support directory.
- **Native push and Settings:** NSApplicationDelegate remote-notification registration, CloudKit notification forwarding, plain sync status and expandable diagnostic details. Existing entitlements remain. Push uses development for Debug and production for Release through the target's `APS_ENVIRONMENT` setting.
- **Providers:** Custom Server service, Keychain API key, model discovery, connection test, output limits, and thinking toggle; ChatGPT Plan service, account/model settings, and local-development availability. Routes cover article/Reddit/comment summaries, thematic analysis, selection Ask AI, Q&A, today/overall/combined summaries, podcast text, whiteboards, and infographics. Mac localhost help uses `127.0.0.1`. Existing Codex/Summarize and PCC/fm options remain available to preserve the Mac bridge.
- **Resilience:** Native ProcessInfo activity assertions; Web AI request timeout, replacement/cancellation, retry timeout renewal, and hidden-page keepalive; Reddit comment retries layered on the Mac rate-limit system, including Retry-After; MLX output caps/timeouts; overall-summary Gemini fallback for local providers; repaired/loose cloud JSON decoding.
- **Library/UI:** Right-click Mark All as Read with confirmation for Reddit, All, Unread, and Today; native Reddit library row; navy sidebar/list/reader values; overall-summary toolbar overlay with fixed scroll clearance; Reddit Q&A scroll-to-section. The running Mac app was not visually inspected, so streaming/scroll smoothness remains a runtime check.
- **Content and selections:** Bounded full-article cache with canonical URL keys, fingerprint validation and TTL; original Mac ad-stripping/anti-block helpers retained; cached Reddit image resolution and image identity deduplication; selection explanation prompts with original source/Q&A context and chunked saved batch evidence; single-feed refresh exposed in subscription context menus; navigation cleanup.
- **Reddit posting:** Edit/submit OAuth scope tracking, reconnect control for old credentials, top-level comment composer, parsed submitted comments/replies, comment-cache invalidation, and immediate visible-thread insertion. The Mac callback flow and desktop composer/layout remain.
- **Podcasts:** Now Playing metadata and media controls for native episode playback; generated podcast audio prepared before playback and reused for export; generation-guarded transcript discard and retained podcast classification. Mac ProcessInfo background support and NSSavePanel export remain. AVAudioSession and iOS background-task APIs were not imported into active Mac paths.

## Preserved Mac work

Desktop trackpad/keyboard navigation, native web-view scroll restoration, scoped storage cleanup, Reddit sort/icon caches, unread caches, full article prompts, Web AI prompt-echo rejection, Foundation Models/PCC Terminal bridge, Shortcuts speech, Mac Kokoro speech, desktop comment layout, YouTube scroll forwarding, and batch podcast export remain. The actual overall-summary implementation is in `ContentView.swift`; the standalone `GlobalSummaryResultView.swift` is outside this target and was left alone.

The iOS widget target and phone-only layouts were not added to the Mac app.

## Validation

- All **58 Mac Swift source files** pass syntax parsing.
- Xcode project and entitlement plists pass `plutil -lint`.
- Targeted compiler typechecks pass for sync/persistence/models, ChatGPT service, Custom Server service/controller/settings, Reddit OAuth/service, and native podcast service. Unrelated app dependencies were supplied as interface stubs where needed; these checks do not constitute a full target build.
- The new behavioral fixture compiles and executes the actual settings, Reddit-media, selection-prompt, and CloudKit merge code. It checks legacy decode defaults, persisted settings, exclusion of the Custom Server key from JSON, token caps, image identity, explanation/Web prompt separation, and newer-removal/stale-upload ordering for favorites/subscriptions. It does not start CloudKit or make network requests.
- **84 regression tests: 75 pass, 8 fail, 1 error.** The 8 failures and 1 error are exactly the baseline failures captured before this port; no new failures remain. Three existing source-level regression checks were updated for the replaced sync/selection implementations.
- A read-only full-source typecheck using existing cached package modules was attempted. Cached package dependency resolution stopped it at a missing `yyjson` module, the subsequent full Xcode Debug build below succeeded.
- iOS reference hashes are unchanged.

## Verified Mac build and launch — 7 October 2026

The native `RSSReaderApp (macOS)` Debug build succeeded after Xcode refreshed the development provisioning profile for iCloud/Push Notifications. The app was opened and its Today window was verified with loaded feed content.

- App: `/Volumes/BackUP /DerivedData-rssmac-port/Build/Products/Debug/RSSReaderApp.app`
- Bundle ID: `com.joaovalente.RSSReaderApp`
- Signature: `codesign --verify --deep --strict` passed.
- Entitlements: development push and `iCloud.com.joaovalente.RSSReaderApp` CloudKit container verified in the signed app.
- Build fixes: attached the Reddit comment sheet to the correct detail view; used the Mac comment-status fields; split Settings provider/sync sections to avoid compiler type-check limits; shared the Mac button style with the ChatGPT panel; corrected the Custom Server panel initializer. The build script now allows Xcode automatic development provisioning updates, and the target records iCloud/Push capabilities.
- Detailed feature and cross-device sync checks remain separate from this successful launch. No release or Production schema deployment was performed.

## Remaining feature/runtime checks

For future builds, keep DerivedData on a volume that has space. `/Volumes/screen` had about 1.2 GiB free at the start; no files were deleted for space.

Verify Mac ↔ iPad reads, favorite/subscription removals, default-install protection, and remote badge updates. Exercise local-server summaries/Q&A and ChatGPT sign-in/inference in an eligible development build. Reconnect Reddit to grant comment permissions. Check media keys/Control Center, podcast playback/export, sidebar confirmations, navy colors, summary scrolling, and desktop back/forward.

Before an App Store release, verify signing/provisioning includes the native push and CloudKit capabilities and deploy the iOS-created CloudKit schema to Production in CloudKit Console. Neither signing nor Production schema acceptance was tested or changed here.

## Incremental file inventory

This compares the result with the saved dirty Mac source baseline, not with Git HEAD.

| File | Change | Lines |
| --- | --- | --- |
| `RSSReaderApp.xcodeproj/project.pbxproj` | Merged | +34 / -0 |
| `RSSReaderApp/Controllers/AppState+ChatGPTPlan.swift` | New | +64 / -0 |
| `RSSReaderApp/Controllers/AppState+OpenAICompatible.swift` | New | +98 / -0 |
| `RSSReaderApp/Controllers/AppState.swift` | Merged | +1510 / -174 |
| `RSSReaderApp/Models/Models.swift` | Merged | +293 / -358 |
| `RSSReaderApp/Podcast/MLXPodcastPlaybackController.swift` | Merged | +52 / -36 |
| `RSSReaderApp/RSSReaderApp.entitlements` | Merged | +10 / -0 |
| `RSSReaderApp/RSSReaderApp.swift` | Merged | +16 / -0 |
| `RSSReaderApp/Services/ChatGPTPlanService.swift` | New | +1404 / -0 |
| `RSSReaderApp/Services/CloudKitSyncManager.swift` | New | +760 / -0 |
| `RSSReaderApp/Services/CloudSyncManager.swift` | Merged | +468 / -211 |
| `RSSReaderApp/Services/FeedService.swift` | Merged | +127 / -18 |
| `RSSReaderApp/Services/GeminiBackgroundTaskManager.swift` | New | +40 / -0 |
| `RSSReaderApp/Services/OpenAICompatibleService.swift` | New | +344 / -0 |
| `RSSReaderApp/Services/PersistenceManager.swift` | Merged | +310 / -240 |
| `RSSReaderApp/Services/PodcastEpisodeService.swift` | Merged | +71 / -2 |
| `RSSReaderApp/Services/RedditOAuthManager.swift` | Merged | +28 / -2 |
| `RSSReaderApp/Services/RedditService.swift` | Merged | +92 / -6 |
| `RSSReaderApp/Services/SummarizeBridge.swift` | Merged | +1 / -0 |
| `RSSReaderApp/Services/SummaryService.swift` | Merged | +266 / -87 |
| `RSSReaderApp/Tests/test_ios_port_behavior.py` | New | +137 / -0 |
| `RSSReaderApp/Tests/test_real_podcast_mac_regressions.py` | Merged | +9 / -4 |
| `RSSReaderApp/Tests/test_selection_origin_context_regressions.py` | Merged | +4 / -2 |
| `RSSReaderApp/Views/AskAIComponents.swift` | Merged | +57 / -8 |
| `RSSReaderApp/Views/ChatGPTPlanSettingsView.swift` | New | +239 / -0 |
| `RSSReaderApp/Views/CommentViews.swift` | Merged | +36 / -11 |
| `RSSReaderApp/Views/ContentView.swift` | Merged | +251 / -49 |
| `RSSReaderApp/Views/OpenAICompatibleSettingsView.swift` | New | +156 / -0 |
| `RSSReaderApp/Views/RedditDetailView.swift` | Merged | +229 / -15 |
| `RSSReaderApp/Views/SettingsView.swift` | Merged | +37 / -138 |
| `RSSReaderApp/Views/SummaryColumnView.swift` | Merged | +14 / -4 |
| `RSSReaderApp/Views/WebAIHandoffView.swift` | Merged | +14 / -0 |

## Baseline regression failures

- test_article_summary_and_qa_wire_both_selection_actions (test_ask_ai_regressions.MacAskAIRegressionTests.test_article_summary_and_qa_wire_both_selection_actions)
- test_ask_ai_sheet_uses_response_formatter (test_ask_ai_regressions.MacAskAIRegressionTests.test_ask_ai_sheet_uses_response_formatter)
- test_card_sanitizer_covers_reddit_and_only_podcast_youtube_article_rows (test_reddit_card_preview.RedditCardPreviewTests.test_card_sanitizer_covers_reddit_and_only_podcast_youtube_article_rows)
- test_compact_feed_previews_fill_the_column_beside_images (test_native_mac_ios_parity_regressions.NativeMacIOSParityRegressionTests.test_compact_feed_previews_fill_the_column_beside_images)
- test_feed_cards_have_wide_and_compact_window_layouts (test_native_mac_ios_parity_regressions.NativeMacIOSParityRegressionTests.test_feed_cards_have_wide_and_compact_window_layouts)
- test_readability_work_is_cached (test_article_reader_loading_fallback.ArticleReaderLoadingFallbackTests.test_readability_work_is_cached)
- test_reddit_comment_summary_wires_both_selection_actions (test_ask_ai_regressions.MacAskAIRegressionTests.test_reddit_comment_summary_wires_both_selection_actions)
- test_reddit_deep_analysis_web_menu_uses_web_override (test_ask_ai_regressions.MacAskAIRegressionTests.test_reddit_deep_analysis_web_menu_uses_web_override)
- test_reddit_summary_and_qa_wire_both_selection_actions (test_ask_ai_regressions.MacAskAIRegressionTests.test_reddit_summary_and_qa_wire_both_selection_actions)
