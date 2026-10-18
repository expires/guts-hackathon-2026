import Foundation

/// The four ways to give Penny your money. One list, used by the connect step of "Play as yourself" and by
/// You > "Connect your money".
enum ConnectKind: String, Equatable, Sendable, CaseIterable, Identifiable {
    case monzo, trading212, statement, manual

    var id: String { rawValue }

    /// The `/v1/connections/{provider}` name. Statement and typed numbers are not connections.
    var provider: String? {
        switch self {
        case .monzo: "monzo"
        case .trading212: "trading212"
        case .statement, .manual: nil
        }
    }

    var title: String {
        switch self {
        case .monzo: "Monzo"
        case .trading212: "Trading 212"
        case .statement: L10n.tr("Upload a statement")
        case .manual: L10n.tr("Enter your numbers")
        }
    }
}

/// View state for the connect step: Monzo, Trading 212, Upload a statement, Enter your numbers.
struct ConnectionsViewState: Equatable, Sendable {
    struct Row: Equatable, Sendable, Identifiable {
        var kind: ConnectKind
        var id: String { kind.rawValue }
        var title: String
        /// What it does, shown while nothing is connected.
        var subtitle: String
        var isConnected: Bool
        /// "Connected" or "Not connected".
        var statusText: String
        /// What it gave us, for example "Transactions since 21 Jul 2026 (151)". Nil when not connected.
        var detail: String?
        /// "Live", "Saved copy". Nil for a statement or typed numbers.
        var badge: String?
        /// The main button: "Connect Monzo", "Connect again", "Upload another".
        var connectTitle: String
        /// Monzo and Trading 212 can be disconnected.
        var canDisconnect: Bool
        var isUnavailable = false
    }

    var phase: LoadPhase = .loading(.init(message: L10n.tr("Checking your connections")))
    var rows: [Row] = []
    /// The option a "Connect ..." button on the stats page points to.
    var highlighted: ConnectKind?
    var isBusy = false
    var errorMessage: String?
    /// One calm line after a change, for example "Trading 212 is connected."
    var notice: String?
    /// "You are using Sample data..." when a sample student is loaded.
    var sampleNote: String?
    var monzoWait: MonzoWait?
    var trading212 = Trading212Sheet()
    /// Waiting for the user to confirm a disconnect.
    var pendingDisconnect: ConnectKind?
    /// "Continue" to the stats page. Nil hides the button (the You tab editor).
    var continueTitle: String?
}

struct ConnectionsActions {
    var onConnect: (ConnectKind) -> Void = { _ in }
    /// Asks for confirmation first.
    var onDisconnect: (ConnectKind) -> Void = { _ in }
    var onConfirmDisconnect: () -> Void = {}
    var onCancelDisconnect: () -> Void = {}
    var onContinue: () -> Void = {}
    var onClose: () -> Void = {}
    var onRetry: () -> Void = {}
    var onDismissError: () -> Void = {}
    var onSubmitTrading212: (_ key: String, _ secret: String) -> Void = { _, _ in }
    var onCloseTrading212: () -> Void = {}
    var onMonzoReopen: () -> Void = {}
    var onMonzoCancel: () -> Void = {}
    var onMonzoRetry: () -> Void = {}

    static var noop: Self { .init() }
}
