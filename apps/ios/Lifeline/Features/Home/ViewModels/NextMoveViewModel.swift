import Foundation
import Observation

/// Loads `GET /v1/next-move` and runs "Do this" (`POST /v1/plan`). ADR 0018.
@MainActor
@Observable
final class NextMoveViewModel {
    static let loadingMessage = "Finding your next money move"

    private let client: any LifelineClient
    private(set) var response: NextMoveResponse?
    private(set) var phase: LoadPhase = .loading(.init(message: NextMoveViewModel.loadingMessage))
    private(set) var plannedMoveIDs: Set<String> = []
    private(set) var planTotal: Double?
    private(set) var addingMoveID: String?
    private(set) var focusedMoveID: String?
    private(set) var planError: String?

    /// Routes. The glue sets them.
    @ObservationIgnored var onTestIt: @MainActor (String) -> Void = { _ in }
    @ObservationIgnored var onWhy: @MainActor (Move) -> Void = { _ in }
    @ObservationIgnored var onOpenPlan: @MainActor () -> Void = {}

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: NextMoveCardState {
        var state = Self.makeState(response: response, phase: phase, plannedMoveIDs: plannedMoveIDs, planTotal: planTotal)
        state.addingMoveID = addingMoveID
        state.focusedMoveID = focusedMoveID
        if let planError { state.planMessage = planError }
        return state
    }

    var actions: NextMoveActions {
        NextMoveActions(
            onTestIt: { [weak self] id in
                guard let self, move(id)?.testable == true else { return }
                onTestIt(id)
            },
            onWhy: { [weak self] id in
                guard let self, let move = move(id) else { return }
                onWhy(move)
            },
            onDoThis: { [weak self] id in Task { await self?.addToPlan(moveID: id) } },
            onFocus: { [weak self] id in self?.focus(id) },
            onOpenPlan: { [weak self] in self?.onOpenPlan() },
            onRetry: { [weak self] in Task { await self?.load() } }
        )
    }

    /// All moves: the top move first, then the runners-up.
    var moves: [Move] {
        guard let response else { return [] }
        return [response.top] + response.runnersUp
    }

    func move(_ id: String) -> Move? {
        moves.first { $0.id == id }
    }

    /// Shows a move in the card. Unknown ids and the top move clear the focus.
    func focus(_ id: String?) {
        guard let id, id != response?.top.id, move(id) != nil else {
            focusedMoveID = nil
            return
        }
        focusedMoveID = id
    }

    func load() async {
        phase = .loading(.init(message: Self.loadingMessage))
        do {
            response = try await client.nextMove()
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
            return
        }
        // The plan marks moves that are already chosen. A plan error does not block the card.
        if let plan = try? await client.plan() {
            plannedMoveIDs = Set(plan.items.map(\.moveId))
            planTotal = plan.items.isEmpty ? nil : plan.totalImpactPerYear
        }
    }

    func addToPlan(moveID: String) async {
        guard addingMoveID == nil, move(moveID) != nil, !plannedMoveIDs.contains(moveID) else { return }
        addingMoveID = moveID
        planError = nil
        defer { addingMoveID = nil }
        do {
            let item = try await client.addPlanItem(moveID: moveID)
            plannedMoveIDs.insert(item.moveId)
            if let plan = try? await client.plan() {
                planTotal = plan.totalImpactPerYear
            } else {
                planTotal = (planTotal ?? 0) + item.impactPerYear
            }
        } catch {
            planError = APIError.map(error).userMessage
        }
    }

    // MARK: Mapping (pure, used by fixtures and tests)

    static func makeState(
        response: NextMoveResponse?,
        phase: LoadPhase,
        plannedMoveIDs: Set<String> = [],
        planTotal: Double? = nil
    ) -> NextMoveCardState {
        guard let response else {
            return NextMoveCardState(
                phase: phase, question: "What is my next money move?", top: nil, runnersUp: [],
                backtestText: nil, isSampleData: false, addingMoveID: nil, planMessage: nil, focusedMoveID: nil
            )
        }
        let planMessage = planTotal.map { total in
            "Added to your plan. Your plan is worth \(Money.format(total)) a year."
        }
        return NextMoveCardState(
            phase: phase,
            question: response.question?.rawValue ?? "What is my next money move?",
            top: move(response.top, isInPlan: plannedMoveIDs.contains(response.top.id)),
            runnersUp: response.runnersUp.map { move($0, isInPlan: plannedMoveIDs.contains($0.id)) },
            backtestText: response.backtest.map(backtestText),
            isSampleData: FinanceMapping.isSample(response.meta),
            addingMoveID: nil,
            planMessage: plannedMoveIDs.isEmpty ? nil : planMessage,
            focusedMoveID: nil
        )
    }

    static func move(_ move: Move, isInPlan: Bool) -> NextMoveCardState.Move {
        NextMoveCardState.Move(
            id: move.id,
            kind: move.kind.rawValue,
            action: move.action,
            headline: move.headline,
            impactPerYear: move.impactPerYear,
            impactText: impactText(move.impactPerYear),
            impactAmountText: Money.format(abs(move.impactPerYear.rounded())),
            impactCaption: move.impactPerYear.rounded() < 0 ? "a year worse off" : "a year better off",
            confidenceWord: confidenceWord(move.confidence),
            confidenceFilled: confidenceFilled(move.confidence),
            worstCaseText: "Worst past period: " + impactText(move.worstCasePerYear),
            confidence: move.confidence,
            confidenceLabel: move.confidenceLabel,
            deadlineText: deadlineText(deadline: move.deadline, daysLeft: move.daysLeft),
            daysLeft: move.daysLeft,
            sources: move.sources.map(StateMapping.sourceChip),
            options: move.options.map { .init(id: $0.id, label: $0.label, isRecommended: $0.isRecommended ?? false) },
            isTestable: move.testable,
            hasLesson: move.conceptId != nil,
            isInPlan: isInPlan
        )
    }

    /// High at 0.75 or more, medium at 0.5 or more, otherwise low.
    static func confidenceWord(_ confidence: Double) -> String {
        confidence >= 0.75 ? "High confidence" : (confidence >= 0.5 ? "Medium confidence" : "Low confidence")
    }

    static func confidenceFilled(_ confidence: Double) -> Int {
        confidence >= 0.75 ? 3 : (confidence >= 0.5 ? 2 : 1)
    }

    /// "£1,240 a year better off", "£310 a year worse off", "No change".
    static func impactText(_ value: Double) -> String {
        let rounded = value.rounded()
        if rounded > 0 { return "\(Money.format(rounded)) a year better off" }
        if rounded < 0 { return "\(Money.format(-rounded)) a year worse off" }
        return "No change a year"
    }

    /// "Decide by 31 Mar 2027 (165 days left)".
    static func deadlineText(deadline: String?, daysLeft: Int?) -> String? {
        switch (deadline, daysLeft) {
        case let (deadline?, days?):
            "Decide by \(FinanceMapping.dayText(deadline)) (\(days == 1 ? "1 day" : "\(days) days") left)"
        case let (deadline?, nil):
            "Decide by \(FinanceMapping.dayText(deadline))"
        case let (nil, days?):
            days == 1 ? "1 day left" : "\(days) days left"
        case (nil, nil):
            nil
        }
    }

    /// "Tested on 58 past cases: right 69% of the time. Always fix for 2 years: 41%."
    static func backtestText(_ backtest: Components.Schemas.NextMoveBacktest) -> String {
        "Tested on \(backtest.n) past cases: right \(FinanceMapping.percent(backtest.hitRate)) of the time. "
            + "\(backtest.baseline): \(FinanceMapping.percent(backtest.baselineHitRate))."
    }
}
