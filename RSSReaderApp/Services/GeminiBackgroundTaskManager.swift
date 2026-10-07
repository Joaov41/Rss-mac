import Foundation

/// Native Mac activity assertion shared by AI requests. Each handle releases its own assertion.
final class GeminiBackgroundTaskManager {
    static let shared = GeminiBackgroundTaskManager()
    enum TaskType { case processing, summarization }
    func taskIdentifier(for type: TaskType) -> String { "RSSReaderApp.\(type)" }
    func beginLongRunningTask(identifier: String, title: String) -> GeminiBackgroundTaskHandle {
        GeminiBackgroundTaskHandle(reason: title)
    }
    func beginTask(title: String, subtitle: String, totalUnitCount: Int64 = 100) -> GeminiBackgroundTaskHandle? {
        GeminiBackgroundTaskHandle(reason: title)
    }
}

final class GeminiBackgroundTaskHandle: @unchecked Sendable {
    private let lock = NSLock()
    private var activity: NSObjectProtocol?
    init(reason: String) {
        activity = ProcessInfo.processInfo.beginActivity(options: [.userInitiated, .idleSystemSleepDisabled], reason: reason)
    }
    func finish(success: Bool) {
        lock.lock()
        let current = activity
        activity = nil
        lock.unlock()
        if let current { ProcessInfo.processInfo.endActivity(current) }
    }
    deinit { finish(success: false) }
}

func withAIBackgroundTask<T>(
    _ title: String,
    isolation: isolated (any Actor)? = #isolation,
    _ operation: () async throws -> T
) async throws -> T {
    let handle = GeminiBackgroundTaskManager.shared.beginLongRunningTask(identifier: "AI", title: title)
    defer { handle.finish(success: true) }
    return try await operation()
}
