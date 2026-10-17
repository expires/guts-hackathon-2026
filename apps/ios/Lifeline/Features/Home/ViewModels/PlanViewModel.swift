import Foundation
import Observation

/// Loads `GET /v1/plan`.
@MainActor
@Observable
final class PlanViewModel {
    static let loadingMessage = "Loading your plan"

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

    static func makeState(plan: PlanResponse?, phase: LoadPhase, isSampleData: Bool) -> PlanViewState {
        let items = (plan?.items ?? []).map { item in
            PlanViewState.Item(
                id: item.id,
                action: item.action,
                impactPerYear: item.impactPerYear,
                impactText: NextMoveViewModel.impactText(item.impactPerYear),
                isDone: item.status == .done,
                addedText: "Added " + FinanceMapping.dayText(item.addedAt)
            )
        }
        let total = plan?.totalImpactPerYear ?? 0
        return PlanViewState(
            phase: phase,
            items: items,
            totalPerYear: total,
            totalText: items.isEmpty
                ? "Your plan is empty. Tap \"Do this\" on a move to add it."
                : "Your plan is worth \(Money.format(total)) a year.",
            isSampleData: isSampleData
        )
    }
}
