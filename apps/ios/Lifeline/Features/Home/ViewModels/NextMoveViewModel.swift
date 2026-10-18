import Foundation
import Observation

/// Loads `GET /v1/next-move` and runs "Do this" (`POST /v1/plan`). ADR 0018.
@MainActor
@Observable
final class NextMoveViewModel {
    static var loadingMessage: String { L10n.tr("Finding your next money move") }

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
    /// Why? scrolled to the sources ("Based on N sources").
    @ObservationIgnored var onWhySources: @MainActor (Move) -> Void = { _ in }
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
            onSources: { [weak self] id in
                guard let self, let move = move(id) else { return }
                onWhySources(move)
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

    /// Uses the move from `GET /v1/finance/home` (no extra request for the card). The plan loads quietly.
    func apply(_ response: NextMoveResponse?) async {
        show(response)
        await loadPlan()
    }

    /// Shows a move at once (cached or fresh home). No network.
    func show(_ response: NextMoveResponse?) {
        self.response = response
        phase = .ready
        if let plan = cachedPlan { applyPlan(plan) }
    }

    /// Skeleton in the card while the move loads on its own (home was sent without `next_move`).
    func showLoading() {
        phase = .loading(.init(message: Self.loadingMessage))
    }

    /// The move could not load and no move is shown: the card shows the error with Try again.
    func showFailure(_ error: APIError) {
        phase = .failed(.from(error))
    }

    private var cachedPlan: PlanResponse?

    private func applyPlan(_ plan: PlanResponse) {
        cachedPlan = plan
        plannedMoveIDs = Set(plan.items.map(\.moveId))
        planTotal = plan.items.isEmpty ? nil : Self.yearlyPlanTotal(plan, moves: moves)
    }

    /// The plan marks ("In plan"), cached first then fresh (ADR 0060). Failures are quiet.
    func loadPlan() async {
        try? await client.load(CachedOps.plan) { [weak self] plan in self?.applyPlan(plan) }
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
            planTotal = plan.items.isEmpty ? nil : Self.yearlyPlanTotal(plan, moves: moves)
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
                planTotal = Self.yearlyPlanTotal(plan, moves: moves)
            } else {
                let yearly = move(item.moveId).map(Self.isYearly) ?? true
                planTotal = (planTotal ?? 0) + (yearly ? item.impactPerYear : 0)
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
                phase: phase, question: L10n.tr("Where should my money go this month?"), top: nil, runnersUp: [],
                backtestText: nil, isSampleData: false, addingMoveID: nil, planMessage: nil, focusedMoveID: nil
            )
        }
        let sourceCount = response.decisionSourceCount ?? 0
        let planMessage = planTotal.map { total in
            L10n.tr("Added to your plan. Your plan is worth \(Money.format(total)) a year.")
        }
        return NextMoveCardState(
            phase: phase,
            question: response.question?.rawValue ?? L10n.tr("Where should my money go this month?"),
            top: move(response.top, isInPlan: plannedMoveIDs.contains(response.top.id)),
            runnersUp: response.runnersUp.map { move($0, isInPlan: plannedMoveIDs.contains($0.id)) },
            backtestText: response.backtest.map(backtestText),
            isSampleData: FinanceMapping.isSample(response.meta),
            addingMoveID: nil,
            planMessage: plannedMoveIDs.isEmpty ? nil : planMessage,
            focusedMoveID: nil,
            sourceCountText: sourceCount > 0 ? (sourceCount == 1 ? L10n.tr("Based on 1 source") : L10n.tr("Based on \(sourceCount) sources")) : nil
        )
    }

    static func move(_ move: Move, isInPlan: Bool) -> NextMoveCardState.Move {
        var state = NextMoveCardState.Move(
            id: move.id,
            kind: move.kind.rawValue,
            action: move.action,
            headline: move.headline,
            impactPerYear: move.impactPerYear,
            impactText: impactText(move.impactPerYear),
            impactAmountText: Money.format(abs(move.impactPerYear.rounded())),
            impactCaption: move.impactPerYear.rounded() < 0 ? L10n.tr("a year worse off") : L10n.tr("a year better off"),
            confidenceWord: confidenceWord(move.confidence),
            confidenceFilled: confidenceFilled(move.confidence),
            worstCaseText: worstCaseText(move.worstCasePerYear),
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
        if let summary = move.tradeOff?.summary, !summary.isEmpty {
            state.tradeOffText = L10n.tr("What you give up: \(summary)")
        }
        state.tradeOffPoints = move.tradeOff?.points.map(\.text) ?? []
        if move.kind.rawValue == "lifetime_isa", isYearly(move), move.impactPerYear.rounded() > 0 {
            // The gain is the government bonus on what you put in, not a yearly saving.
            state.impactAmountText = Money.format(move.impactPerYear.rounded())
            state.impactCaption = L10n.tr("government bonus")
            state.impactText = L10n.tr("\(state.impactAmountText) government bonus")
        }
        if move.gainKind == .weeksOfCover {
            // Weekly budget (F-R-1): never a £ a year figure.
            state.isMonthsOfCover = true
            state.worstCaseText = ""
            if let shortfall = move.shortfall, shortfall.rounded() > 0 {
                let amount = Money.format(shortfall.rounded())
                state.impactAmountText = amount
                if let deadline = move.deadline {
                    let date = longDayText(deadline)
                    state.impactCaption = L10n.tr("short before \(date)")
                    state.impactText = L10n.tr("\(amount) short before \(date)")
                } else {
                    state.impactCaption = L10n.tr("short before your next money")
                    state.impactText = L10n.tr("\(amount) short before your next money")
                }
            } else if let weekly = move.safeWeeklySpend {
                let amount = Money.format(weekly.rounded())
                state.impactAmountText = amount
                if let weeks = move.coverWeeks.map(weeksText) {
                    state.impactCaption = L10n.tr("Spend up to this a week. \(weeks) until your next money")
                    state.impactText = L10n.tr("Spend up to \(amount) a week. \(weeks) until your next money")
                } else {
                    state.impactCaption = L10n.tr("Spend up to this a week")
                    state.impactText = L10n.tr("Spend up to \(amount) a week")
                }
            } else {
                state.impactAmountText = ""
                state.impactCaption = missingCostsText
                state.impactText = missingCostsText
                state.isGainMissing = true
            }
        } else if move.gainKind == .monthsOfCover {
            state.worstCaseText = ""
            state.isMonthsOfCover = true
            if let months = move.coverMonths {
                let amount = monthsText(months)
                state.impactAmountText = amount
                state.impactCaption = L10n.tr("of cover")
                state.impactText = L10n.tr("\(amount) of cover")
            } else {
                // No monthly costs entered: never invent a number (bug 5, ADR 0053).
                state.impactAmountText = ""
                state.impactCaption = missingCostsText
                state.impactText = missingCostsText
                state.isGainMissing = true
            }
        }
        // Plain-English confidence (ADR 0069): the engine's `confidence_text`, else a sentence from its level.
        // Never "Medium · sample 4".
        state.confidenceText = confidenceText(move)
        if let level = move.confidenceLevel {
            state.confidenceWord = switch level {
            case .high: L10n.tr("High confidence")
            case .medium: L10n.tr("Medium confidence")
            case .low: L10n.tr("Low confidence")
            }
            state.confidenceFilled = switch level {
            case .high: 3
            case .medium: 2
            case .low: 1
            }
        } else {
            // No engine level (fallback move): no meter and no level word (F2-3).
            state.confidenceWord = ""
            state.confidenceFilled = 0
            state.confidenceLabel = ""
        }
        return state
    }

    /// "Medium confidence: based on your last 4 weeks of spending" (the engine's `confidence_text`).
    /// Without it, a plain sentence from `confidence_level`. Without a level either, empty (the card hides it).
    static func confidenceText(_ move: Move) -> String {
        if let text = move.confidenceText?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty {
            return text
        }
        guard let level = move.confidenceLevel else { return "" }
        return switch level {
        case .high: L10n.tr("High confidence: Penny has seen this work in many similar cases.")
        case .medium: L10n.tr("Medium confidence: Penny has some similar cases to go on.")
        case .low: L10n.tr("Low confidence: Penny has only a few similar cases. Use it as a rough guide.")
        }
    }

    static var missingCostsText: String { L10n.tr("Add your monthly costs to see this") }

    /// True when the move's gain is £ a year. Weekly budget and cover moves are not (F-R-1).
    static func isYearly(_ move: Move) -> Bool {
        move.gainKind == nil || move.gainKind == .gbpPerYear
    }

    /// The plan total in £ a year: only items whose move gains £ a year (a weekly budget is not a yearly gain).
    static func yearlyPlanTotal(_ plan: PlanResponse, moves: [Move]) -> Double {
        plan.items.reduce(0) { total, item in
            if let move = moves.first(where: { $0.id == item.moveId }) {
                return isYearly(move) ? total + item.impactPerYear : total
            }
            return PlanViewModel.isYearlyKind(item.kind.rawValue) ? total + item.impactPerYear : total
        }
    }

    /// "3 weeks", "1 week", "2.5 weeks".
    static func weeksText(_ weeks: Double) -> String {
        let rounded = (weeks * 10).rounded() / 10
        let number = rounded.formatted(.number.precision(.fractionLength(0...1)).locale(Money.locale))
        return rounded == 1 ? L10n.tr("1 week") : L10n.tr("\(number) weeks")
    }

    /// "2 November".
    static func longDayText(_ raw: String) -> String {
        guard let date = FinanceMapping.date(raw) else { return raw }
        var format = Date.FormatStyle(date: .omitted, time: .omitted).locale(FinanceMapping.dateLocale).day().month(.wide)
        format.timeZone = TimeZone(identifier: "UTC") ?? .gmt
        return date.formatted(format)
    }

    /// "4 months", "1 month", "4.5 months".
    static func monthsText(_ months: Double) -> String {
        let rounded = (months * 10).rounded() / 10
        let number = rounded.formatted(.number.precision(.fractionLength(0...1)).locale(Money.locale))
        return rounded == 1 ? L10n.tr("1 month") : L10n.tr("\(number) months")
    }

    /// High at 0.75 or more, medium at 0.5 or more, otherwise low.
    static func confidenceWord(_ confidence: Double) -> String {
        confidence >= 0.75 ? L10n.tr("High confidence") : (confidence >= 0.5 ? L10n.tr("Medium confidence") : L10n.tr("Low confidence"))
    }

    static func confidenceFilled(_ confidence: Double) -> Int {
        confidence >= 0.75 ? 3 : (confidence >= 0.5 ? 2 : 1)
    }

    /// "Worst past period: £310 a year worse off" as one sentence per direction.
    static func worstCaseText(_ value: Double) -> String {
        let rounded = value.rounded()
        if rounded > 0 { return L10n.tr("Worst past period: \(Money.format(rounded)) a year better off") }
        if rounded < 0 { return L10n.tr("Worst past period: \(Money.format(-rounded)) a year worse off") }
        return L10n.tr("Worst past period: no change a year")
    }

    /// "£1,240 a year better off", "£310 a year worse off", "No change".
    static func impactText(_ value: Double) -> String {
        let rounded = value.rounded()
        if rounded > 0 { return L10n.tr("\(Money.format(rounded)) a year better off") }
        if rounded < 0 { return L10n.tr("\(Money.format(-rounded)) a year worse off") }
        return L10n.tr("No change a year")
    }

    /// "Decide by 31 Mar 2027 (165 days left)".
    static func deadlineText(deadline: String?, daysLeft: Int?) -> String? {
        switch (deadline, daysLeft) {
        case let (deadline?, days?):
            days == 1
                ? L10n.tr("Decide by \(FinanceMapping.dayText(deadline)) (1 day left)")
                : L10n.tr("Decide by \(FinanceMapping.dayText(deadline)) (\(days) days left)")
        case let (deadline?, nil):
            L10n.tr("Decide by \(FinanceMapping.dayText(deadline))")
        case let (nil, days?):
            days == 1 ? L10n.tr("1 day left") : L10n.tr("\(days) days left")
        case (nil, nil):
            nil
        }
    }

    /// "Tested on 58 past cases: right 69% of the time. Always fix for 2 years: 41%."
    static func backtestText(_ backtest: Components.Schemas.NextMoveBacktest) -> String {
        L10n.tr("Tested on \(backtest.n) past cases: right \(FinanceMapping.percent(backtest.hitRate)) of the time. \(backtest.baseline): \(FinanceMapping.percent(backtest.baselineHitRate)).")
    }
}
