import Foundation

struct SourcesViewState: Equatable, Sendable {
    struct Row: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var status: DataStatus
        /// For example "Updated 17 Oct 2026, 11:00".
        var updatedText: String?
        var coverage: String
        var attribution: String
        var licence: String
        var needsKey: Bool
        var lastError: String?
    }

    var phase: LoadPhase
    var rows: [Row]
    var usesSampleData: Bool
}

struct SourcesActions {
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
