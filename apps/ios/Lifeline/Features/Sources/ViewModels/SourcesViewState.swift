import Foundation

/// "Why no bank connection" (DIRECTION_V2 section 2): plain English, one point per line.
enum BankConnectionNote {
    static var title: String { L10n.tr("Why no bank connection") }
    static var points: [String] { [
        L10n.tr("Monzo's API is for personal use only, so an app cannot use it for other people."),
        L10n.tr("Open Banking needs FCA authorisation or a contract with an aggregator."),
        L10n.tr("GoCardless closed new sign-ups to its bank data service in 2025."),
        L10n.tr("Apple FinanceKit needs a special entitlement from Apple."),
        "A statement upload uses the same data format, so a bank feed can plug in later.",
    ] }
}

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
