import Foundation

/// Accounts screen: Monzo and Trading212, their status and the actions to connect or disconnect.
struct AccountsViewState: Equatable, Sendable {
    enum HistoryKind: Equatable, Sendable {
        /// Imported. "History imported back to 18 Oct 2024".
        case imported
        /// Waiting for the user to approve access in the Monzo app.
        case waitingForApproval
        /// Not imported and not waiting for approval.
        case problem
    }

    struct Row: Equatable, Sendable, Identifiable {
        /// Provider raw value: "monzo" or "trading212".
        var id: String
        var name: String
        var systemImage: String
        /// What the account is for, in plain English.
        var subtitle: String
        var isConnected: Bool
        /// "Live", "Sample data" or "Not connected".
        var statusText: String
        var isSample: Bool
        /// "Account …a1b2".
        var hintText: String?
        var historyText: String?
        var historyKind: HistoryKind?
        var isBusy: Bool
    }

    enum BannerKind: Equatable, Sendable { case success, error, info }

    struct Banner: Equatable, Sendable {
        var kind: BannerKind
        var text: String
    }

    struct Trading212Form: Equatable, Sendable {
        var isSubmitting: Bool
        var errorText: String?
        var guidance: String
    }

    struct DisconnectPrompt: Equatable, Sendable {
        var providerID: String
        var title: String
        var message: String
        var confirmTitle: String
    }

    var phase: LoadPhase
    var rows: [Row]
    var banner: Banner?
    /// Shown after "Connect" on Monzo: how the emailed sign-in works.
    var monzoGuidance: String?
    /// "Approve the request in your Monzo app. Your history imports automatically once you do."
    var approvalNote: String?
    var showsImportNow: Bool
    var isImporting: Bool
    var trading212Form: Trading212Form?
    var disconnectPrompt: DisconnectPrompt?
}

struct AccountsActions {
    var onConnectMonzo: @MainActor () -> Void = {}
    var onConnectTrading212: @MainActor () -> Void = {}
    /// Key and secret are sent once and never stored. The View clears its fields right after.
    var onSubmitTrading212: @MainActor (_ apiKey: String, _ apiSecret: String) -> Void = { _, _ in }
    var onCancelTrading212: @MainActor () -> Void = {}
    var onImportNow: @MainActor () -> Void = {}
    var onRequestDisconnect: @MainActor (String) -> Void = { _ in }
    var onConfirmDisconnect: @MainActor () -> Void = {}
    var onCancelDisconnect: @MainActor () -> Void = {}
    var onDismissBanner: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
