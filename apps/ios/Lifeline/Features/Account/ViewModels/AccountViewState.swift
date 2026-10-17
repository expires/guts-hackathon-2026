import Foundation

/// Account screen: who you are, how you signed in, what data we hold, and the account actions.
struct AccountViewState: Equatable, Sendable {
    struct Profile: Equatable, Sendable {
        var name: String
        /// "Signed in with Apple" or "Demo account on this phone".
        var signInText: String
        /// "Since 17 Oct 2026".
        var sinceText: String
        /// "Statement", "Your numbers", "Monzo", "Shortcuts".
        var dataSources: [String]
        var hasFinanceData: Bool
    }

    enum Confirm: String, Equatable, Sendable {
        case delete, reset, signOut

        var title: String {
            switch self {
            case .delete: "Delete your account?"
            case .reset: "Reset the demo?"
            case .signOut: "Sign out?"
            }
        }

        var message: String {
            switch self {
            case .delete: "This removes your account and every record we hold: lives, plan, guesses and money data. You cannot undo it."
            case .reset: "This clears your lives, plan, guesses and money data. Your account stays."
            case .signOut: "You can sign in again at any time. Your data stays on the server."
            }
        }

        var button: String {
            switch self {
            case .delete: "Delete my account"
            case .reset: "Reset"
            case .signOut: "Sign out"
            }
        }
    }

    var phase: LoadPhase = .loading(.standard)
    var profile: Profile?
    var confirm: Confirm?
    var isBusy = false
    /// "Demo data cleared." after a reset.
    var message: String?
    var errorMessage: String?
    var isSampleData = false
}

struct AccountActions {
    var onAsk: (AccountViewState.Confirm) -> Void = { _ in }
    var onConfirm: () -> Void = {}
    var onCancel: () -> Void = {}
    var onRetry: () -> Void = {}
    var onClose: (() -> Void)?

    static var noop: AccountActions { AccountActions() }
}
