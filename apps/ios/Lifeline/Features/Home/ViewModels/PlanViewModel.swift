import Foundation
import Observation

/// Loads `GET /v1/plan`.
@MainActor
@Observable
final class PlanViewModel {
    static var loadingMessage: String { L10n.tr("Loading your plan") }

    private let client: any LifelineClient
    private(set) var plan: PlanResponse?
    private(set) var phase: LoadPhase = .loading(.init(message: PlanViewModel.loadingMessage))
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: PlanViewState {
        Self.makeState(plan: plan, phase: phase, isSampleData: client.kind == .mock)
    }

    var actions: PlanActions {
        PlanActions(
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    func load() async {
        phase = .loading(.init(message: Self.loadingMessage))
        do {
            plan = try await client.plan()
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    /// Move kinds whose gain is not £ a year (weekly budget, months of cover). Used when the move is not loaded.
    static let nonYearlyKinds: Set<String> = ["weekly_budget", "build_emergency_fund", "keep_cash"]

    static func isYearlyKind(_ kind: String) -> Bool {
        !nonYearlyKinds.contains(kind)
    }

    static func makeState(plan: PlanResponse?, phase: LoadPhase, isSampleData: Bool) -> PlanViewState {
        let items = (plan?.items ?? []).map { item in
            let yearly = isYearlyKind(item.kind.rawValue)
            return PlanViewState.Item(
                id: item.id,
                action: item.action,
                impactPerYear: yearly ? item.impactPerYear : 0,
                impactText: yearly ? NextMoveViewModel.impactText(item.impactPerYear) : "",
                isDone: item.status == .done,
                addedText: L10n.tr("Added \(FinanceMapping.dayText(item.addedAt))")
            )
        }
        // Only £ a year gains count in the yearly total (F-R-1).
        let total = (plan?.items ?? []).filter { isYearlyKind($0.kind.rawValue) }.reduce(0) { $0 + $1.impactPerYear }
        return PlanViewState(
            phase: phase,
            items: items,
            totalPerYear: total,
            totalText: items.isEmpty
                ? L10n.tr("Your plan is empty. Tap \"Do this\" on a move to add it.")
                : L10n.tr("Your plan is worth \(Money.format(total)) a year."),
            isSampleData: isSampleData
        )
    }
}
