import Foundation
import Observation

@MainActor
@Observable
final class MoneyTabViewModel {
    private let session: GameSession
    /// Closes the menu sheet. An action also closes it, so its result shows on the Life screen.
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(session: GameSession) {
        self.session = session
    }

    var state: MoneyTabViewState {
        Self.makeState(life: session.life, isBusy: session.isBusy, outcome: ActionTabSupport.outcome(session))
    }

    var actions: ActionTabActions {
        ActionTabActions(
            onAction: { [weak self] in
                guard let self else { return }
                ActionTabSupport.perform(session, tab: .money, actionID: $0)
                onClose()
            },
            onDismissOutcome: { [weak self] in self?.session.dismissOutcome() },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    static func makeState(life: Life?, isBusy: Bool, outcome: OutcomeState?) -> MoneyTabViewState {
        guard let finances = life?.finances else {
            return MoneyTabViewState(netWorth: 0, annualIncome: 0, monthlyCosts: 0, have: [], owe: [], mortgageNote: nil, actions: [], isBusy: isBusy, outcome: outcome)
        }
        let have: [MoneyTabViewState.Row] = [
            .init(id: "cash", label: "Cash", value: finances.cash),
            .init(id: "savings", label: "Savings", value: finances.savings),
            .init(id: "investments", label: "Investments", value: finances.investments),
            .init(id: "crypto", label: "Crypto", value: finances.crypto),
            .init(id: "pension", label: "Pension", value: finances.pension),
            .init(id: "home", label: L10n.tr("Home value"), value: finances.propertyValue),
        ].filter { $0.value != 0 || $0.id == "cash" }
        let owe: [MoneyTabViewState.Row] = [
            .init(id: "mortgage", label: "Mortgage", value: finances.mortgageBalance),
            .init(id: "debt", label: L10n.tr("Loans and cards"), value: finances.otherDebt),
            .init(id: "studentLoan", label: L10n.tr("Student loan"), value: finances.studentLoan),
        ].filter { $0.value != 0 }
        var mortgageNote: String?
        if let rate = finances.mortgageRate, finances.mortgageBalance > 0 {
            let percent = rate.formatted(.number.precision(.fractionLength(0...2)))
            mortgageNote = finances.mortgageFixedUntil.map { L10n.tr("Mortgage rate \(percent)%, fixed until \(String($0))") }
                ?? L10n.tr("Mortgage rate \(percent)%")
        }
        return MoneyTabViewState(
            netWorth: finances.netWorth,
            annualIncome: finances.annualIncome,
            monthlyCosts: finances.monthlyCosts,
            have: have,
            owe: owe,
            mortgageNote: mortgageNote,
            actions: StateMapping.actions(life, tab: .money),
            isBusy: isBusy,
            outcome: outcome
        )
    }
}
