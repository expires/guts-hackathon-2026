import Foundation
import Observation

// Minimal ViewModel created by W6 in the ADR 0011 restructure. W7 owns it and adds the
// consent redirect (lifeline://connected) handling.

/// Connect a bank to prefill "Play yourself" (`/v1/bank/auth-link`, `/v1/bank/summary`).
@MainActor
@Observable
final class BankConnectViewModel {
    private let client: any LifelineClient
    private(set) var step: BankConnectViewState.Step = .intro
    private(set) var link: BankAuthLink?
    private(set) var summary: BankSummary?
    /// Live mode: the consent URL to open. The glue opens it.
    private(set) var consentURL: URL?
    @ObservationIgnored var onUseProfile: @MainActor (DecisionProfile, DataStatus) -> Void = { _, _ in }
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: BankConnectViewState {
        Self.makeState(step: step, link: link, summary: summary)
    }

    var actions: BankConnectActions {
        BankConnectActions(
            onConnect: { [weak self] in Task { await self?.connect() } },
            onUseProfile: { [weak self] in
                guard let self, let summary else { return }
                onUseProfile(summary.profile, StateMapping.status(summary.status.rawValue))
            },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    /// Gets the consent link. With a mock provider there is no redirect, so it loads the summary at once.
    func connect() async {
        step = .connecting
        do {
            let link = try await client.bankAuthLink()
            self.link = link
            if link.status == .mock || client.kind == .mock {
                summary = try await client.bankSummary(session: link.state)
                step = .connected
            } else {
                consentURL = URL(string: link.url)
            }
        } catch {
            step = .failed(.from(APIError.map(error)))
        }
    }

    /// Called after the `lifeline://connected?session=...` redirect.
    func finish(session: String) async {
        do {
            summary = try await client.bankSummary(session: session)
            step = .connected
        } catch {
            step = .failed(.from(APIError.map(error)))
        }
    }

    static func makeState(step: BankConnectViewState.Step, link: BankAuthLink?, summary: BankSummary?) -> BankConnectViewState {
        BankConnectViewState(
            step: step,
            providerName: (summary?.provider ?? link?.provider ?? "your bank").capitalized,
            status: (summary?.status.rawValue ?? link?.status.rawValue).map(StateMapping.status),
            summary: summary.map {
                .init(
                    accounts: $0.accounts,
                    annualIncome: $0.profile.annualIncome,
                    savings: $0.profile.savings,
                    housingLabel: HousingOption(rawValue: $0.profile.housing.rawValue)?.label ?? $0.profile.housing.rawValue,
                    regionLabel: UKRegion(rawValue: $0.profile.region)?.displayName ?? $0.profile.region
                )
            },
            privacyNote: "We read your balances once to fill in the form. We never see your login, and nothing is stored in the app."
        )
    }
}
