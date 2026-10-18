import Foundation
import Observation

/// Account (ADR 0029): `GET /v1/me`, sign out, delete account, demo reset. Every destructive action asks first.
@MainActor
@Observable
final class AccountViewModel {
    private let api: AccountAPI
    private(set) var state: AccountViewState
    @ObservationIgnored var onSignedOut: @MainActor () -> Void = {}
    @ObservationIgnored var onClose: (@MainActor () -> Void)?

    init(api: AccountAPI, isSampleData: Bool) {
        self.api = api
        state = AccountViewState(isSampleData: isSampleData)
    }

    var actions: AccountActions {
        AccountActions(
            onAsk: { [weak self] confirm in
                self?.state.message = nil
                self?.state.errorMessage = nil
                self?.state.confirm = confirm
            },
            onConfirm: { [weak self] in Task { await self?.confirm() } },
            onCancel: { [weak self] in self?.state.confirm = nil },
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: onClose.map { close in { close() } }
        )
    }

    func load() async {
        state.phase = .loading(.standard)
        do {
            state.profile = Self.profile(try await api.getMe())
            state.phase = .ready
        } catch {
            state.phase = .failed(.from(APIError.map(error)))
        }
    }

    func confirm() async {
        guard let confirm = state.confirm else { return }
        state.isBusy = true
        defer { state.isBusy = false }
        do {
            switch confirm {
            case .reset:
                state.profile = Self.profile(try await api.resetDemo())
                state.message = L10n.tr("Demo data cleared. Connect your money again to get a Next Move.")
            case .signOut:
                try await api.signOut()
                onSignedOut()
            case .delete:
                try await api.deleteAccount()
                state.profile = nil
                onSignedOut()
            }
            state.confirm = nil
        } catch {
            state.errorMessage = APIError.map(error).userMessage
        }
    }

    static func profile(_ me: Components.Schemas.Me) -> AccountViewState.Profile {
        let since: String = {
            let parser = ISO8601DateFormatter()
            guard let date = parser.date(from: me.createdAt) ?? FinanceMapping.date(String(me.createdAt.prefix(10))) else { return "" }
            return L10n.tr("Since \(date.formatted(Date.FormatStyle(date: .abbreviated, time: .omitted).locale(FinanceMapping.dateLocale)))")
        }()
        return .init(
            name: me.displayName.flatMap { $0.isEmpty ? nil : $0 } ?? "You",
            signInText: me.authProvider == .apple ? L10n.tr("Signed in with Apple") : L10n.tr("Demo account on this phone"),
            sinceText: since,
            dataSources: me.financeInputs.map { input in
                switch input {
                case .statement: "Statement"
                case .manual: "Your numbers"
                case .bank: "Bank"
                case .appIntent: "Shortcuts"
                case .sample: "Sample statement"
                }
            },
            hasFinanceData: me.hasFinanceData
        )
    }
}

/// Account fixtures for previews, the Playground and tests (contract example `Me`).
@MainActor
enum AccountFixtures {
    static var ready: AccountViewState {
        var state = AccountViewState(isSampleData: true)
        state.profile = AccountViewModel.profile(OnboardingExamples.me)
        state.phase = .ready
        return state
    }

    static var confirmDelete: AccountViewState {
        var state = ready
        state.confirm = .delete
        return state
    }

    static var afterReset: AccountViewState {
        var state = ready
        state.profile?.dataSources = []
        state.profile?.hasFinanceData = false
        state.message = L10n.tr("Demo data cleared. Connect your money again to get a Next Move.")
        return state
    }

    static var loading: AccountViewState { AccountViewState(isSampleData: true) }

    static var error: AccountViewState {
        var state = AccountViewState(isSampleData: true)
        state.phase = .failed(.from(.network))
        return state
    }

    static var all: [(id: String, title: String, state: AccountViewState)] {
        [
            ("ready", "Account", ready),
            ("confirmDelete", L10n.tr("Delete, confirm"), confirmDelete),
            ("afterReset", L10n.tr("After demo reset"), afterReset),
            ("loading", "Loading", loading),
            ("error", "Offline", error),
        ]
    }
}
