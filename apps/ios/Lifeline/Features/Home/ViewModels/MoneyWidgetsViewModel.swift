import Foundation
import Observation

/// Loads the Money tab widgets in parallel (ADR 0016). Each widget fails on its own.
@MainActor
@Observable
final class MoneyWidgetsViewModel {
    private let client: any LifelineClient

    private(set) var overview: Result<FinanceOverview, APIError>?
    private(set) var spending: Result<SpendingResponse, APIError>?
    private(set) var subscriptions: Result<SubscriptionsResponse, APIError>?
    private(set) var bills: Result<BillsResponse, APIError>?
    private(set) var budgets: Result<BudgetsResponse, APIError>?
    private(set) var goals: Result<GoalsResponse, APIError>?
    /// Moves from the Next Move card. Widgets link to the first move of a related kind.
    var moves: [Move] = []

    @ObservationIgnored var onShowMove: @MainActor (String) -> Void = { _ in }

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: MoneyWidgetsViewState {
        Self.makeState(
            overview: overview, spending: spending, subscriptions: subscriptions,
            bills: bills, budgets: budgets, goals: goals, moves: moves
        )
    }

    var actions: MoneyWidgetsActions {
        MoneyWidgetsActions(
            onShowMove: { [weak self] in self?.onShowMove($0) },
            onRetry: { [weak self] in Task { await self?.load() } }
        )
    }

    private var hasLoaded = false

    /// First call loads every widget. Money home calls it after `GET /v1/finance/home` (ADR 0070).
    func loadIfNeeded() async {
        guard !hasLoaded else { return }
        hasLoaded = true
        await load()
    }

    func load() async {
        hasLoaded = true
        // Cached values show at once; skeletons only for parts with no value yet (ADR 0060).
        let client = self.client
        async let overview: Void = cachedLoad(CachedOps.financeOverview) { [weak self] in self?.overview = $0 }
        async let spending: Void = cachedLoad(CachedOps.spending()) { [weak self] in self?.spending = $0 }
        async let subscriptions: Void = cachedLoad(CachedOps.subscriptions) { [weak self] in self?.subscriptions = $0 }
        async let bills: Void = cachedLoad(CachedOps.bills) { [weak self] in self?.bills = $0 }
        async let budgets: Void = cachedLoad(CachedOps.budgets) { [weak self] in self?.budgets = $0 }
        async let goals: Void = cachedLoad(CachedOps.goals) { [weak self] in self?.goals = $0 }
        _ = await (overview, spending, subscriptions, bills, budgets, goals)
    }

    /// `client.load` into a `Result` slot: success with each value; failure only when nothing could be shown.
    private func cachedLoad<T>(
        _ op: CachedOp<T>,
        set: @escaping @MainActor @Sendable (Result<T, APIError>) -> Void
    ) async {
        do {
            try await client.load(op) { value in set(.success(value)) }
        } catch {
            set(.failure(APIError.map(error)))
        }
    }

    // MARK: Move links (ADR 0018)

    enum Widget: CaseIterable {
        case overview, spending, subscriptions, bills, budgets, goals, guess

        /// Move kinds that relate to this widget, in order of preference.
        var moveKinds: [String] {
            switch self {
            case .overview: ["move_savings", "pay_off_debt"]
            case .spending: ["cut_budget"]
            case .subscriptions: ["cancel_subscription", "switch_subscription"]
            case .bills: ["fix_mortgage", "remortgage", "switch_energy"]
            case .budgets: ["cut_budget"]
            case .goals: ["build_emergency_fund", "move_savings"]
            case .guess: ["cut_budget"]
            }
        }
    }

    /// The engine's top move (first in `moves`): "Your next move: Take a tracker". Never a stored text.
    static func topMoveLink(moves: [Move]) -> MoveLinkState? {
        moves.first.map { .init(moveID: $0.id, text: L10n.tr("Your next move: \($0.action)")) }
    }

    static func moveLink(for widget: Widget, moves: [Move]) -> MoveLinkState? {
        for kind in widget.moveKinds {
            if let move = moves.first(where: { $0.kind.rawValue == kind }) {
                let impact = move.impactPerYear.rounded()
                // Weekly budget and cover moves have no £ a year gain (F-R-1).
                let action = move.action
                let text = impact > 0 && NextMoveViewModel.isYearly(move)
                    ? L10n.tr("Your next move: \(action) (\(Money.format(impact)) a year)")
                    : L10n.tr("Your next move: \(action)")
                return MoveLinkState(moveID: move.id, text: text)
            }
        }
        return nil
    }

    // MARK: Mapping (pure, used by fixtures and tests)

    static func makeState(
        overview: Result<FinanceOverview, APIError>?,
        spending: Result<SpendingResponse, APIError>?,
        subscriptions: Result<SubscriptionsResponse, APIError>?,
        bills: Result<BillsResponse, APIError>?,
        budgets: Result<BudgetsResponse, APIError>?,
        goals: Result<GoalsResponse, APIError>?,
        moves: [Move]
    ) -> MoneyWidgetsViewState {
        let metas: [FinanceMeta?] = [
            try? overview?.get().meta, try? spending?.get().meta, try? subscriptions?.get().meta,
            try? bills?.get().meta, try? budgets?.get().meta, try? goals?.get().meta,
        ]
        var billsSection = section(bills, link: moveLink(for: .bills, moves: moves), map: Self.bills)
        // A bill that is also a subscription with a price rise gets the "Up £2" chip.
        if let subs = try? subscriptions?.get(), var value = billsSection.value {
            for index in value.items.indices {
                let name = value.items[index].name
                value.items[index].priceRiseChip = subs.items.first { $0.merchant == name }.flatMap { priceRiseChip($0.priceRise) }
            }
            billsSection.value = value
        }
        return MoneyWidgetsViewState(
            overview: section(overview, link: moveLink(for: .overview, moves: moves), map: Self.overview),
            spending: section(spending, link: moveLink(for: .spending, moves: moves), map: Self.spending),
            subscriptions: section(subscriptions, link: moveLink(for: .subscriptions, moves: moves), map: Self.subscriptions),
            bills: billsSection,
            budgets: section(budgets, link: moveLink(for: .budgets, moves: moves), map: Self.budgets),
            goals: section(goals, link: moveLink(for: .goals, moves: moves)) { $0.items.map(Self.goal) },
            isSampleData: metas.compactMap { $0 }.contains(where: FinanceMapping.isSample)
        )
    }

    private static func section<T, V: Equatable & Sendable>(
        _ result: Result<T, APIError>?,
        link: MoveLinkState?,
        map: (T) -> V
    ) -> WidgetSection<V> {
        switch result {
        case nil: .loading
        case let .success(value): .init(phase: .ready, value: map(value), moveLink: link)
        case let .failure(error): .init(phase: .failed(.from(error)), value: nil, moveLink: nil)
        }
    }

    static func overview(_ response: FinanceOverview) -> MoneyWidgetsViewState.Overview {
        let source = SourceChipState(
            id: "\(response.meta.source).overview",
            name: StateMapping.sourceName(response.meta.source),
            status: StateMapping.status(response.meta.dataStatus.rawValue)
        )
        var overview = MoneyWidgetsViewState.Overview(
            balance: response.balance,
            netWorth: response.netWorth,
            balanceChart: ChartState(
                kind: .line, title: "Balance", xLabel: "Date", yLabel: "£",
                points: FinanceMapping.chartPoints(response.balanceHistory), source: source
            ),
            netWorthChart: ChartState(
                kind: .line, title: "Net worth", xLabel: "Date", yLabel: "£",
                points: FinanceMapping.chartPoints(response.netWorthHistory), source: source
            ),
            accounts: response.accounts.map {
                .init(id: $0.id, name: $0.name, provider: $0.provider, kindLabel: accountKind($0.kind.rawValue), balance: $0.balance)
            },
            netWorthSeries: response.netWorthHistory.map(\.value),
            netWorthChangeText: netWorthChange(response.netWorthHistory),
            monthLabels: response.netWorthHistory.map { FinanceMapping.shortMonthText($0.date) },
            asOfText: L10n.tr("As of \(FinanceMapping.dayText(response.meta.asOf))")
        )
        overview.balanceParts = (response.balanceParts ?? []).enumerated().map { .init(id: $0, label: $1.label, amount: $1.amount) }
        overview.netWorthParts = (response.netWorthParts ?? []).enumerated().map { .init(id: $0, label: $1.label, amount: $1.amount) }
        return overview
    }

    /// "Up £648 since Aug", "Down £120 since Aug".
    static func netWorthChange(_ points: [Components.Schemas.Point]) -> String? {
        guard let first = points.first, let last = points.last, points.count >= 2 else { return nil }
        let change = (last.value - first.value).rounded()
        let since = FinanceMapping.shortMonthText(first.date)
        if change == 0 { return L10n.tr("No change since \(since)") }
        let amount = Money.format(abs(change))
        return change > 0 ? L10n.tr("Up \(amount) since \(since)") : L10n.tr("Down \(amount) since \(since)")
    }

    /// Spending category to a life area colour.
    static func area(_ category: String) -> String {
        switch category {
        case "groceries", "eating_out", "gifts", "entertainment": "family"
        case "transport", "travel", "education": "work"
        case "housing", "bills", "subscriptions": "home"
        case "health", "personal_care": "health"
        case "savings", "income", "transfers": "money"
        default: "other"
        }
    }

    /// "Up £2" for a price rise.
    static func priceRiseChip(_ rise: Components.Schemas.PriceRise?) -> String? {
        guard let rise else { return nil }
        let change = rise.toAmount - rise.fromAmount
        let text = abs(change) < 1 ? FinanceMapping.pounds(abs(change)) : Money.format(abs(change).rounded())
        return "\(change >= 0 ? "Up" : "Down") \(text)"
    }

    static func accountKind(_ raw: String) -> String {
        switch raw {
        case "current": "Current account"
        case "savings": "Savings"
        case "credit": "Credit card"
        case "isa": "ISA"
        case "pension": "Pension"
        case "mortgage": "Mortgage"
        case "loan": "Loan"
        default: raw.capitalized
        }
    }

    static func spending(_ response: SpendingResponse) -> MoneyWidgetsViewState.Spending {
        .init(
            monthText: FinanceMapping.monthText(response.month),
            total: response.total,
            // A category at £0 (rounded) is hidden: no empty legend rows or zero-width bar parts (ADR 0070).
            categories: response.categories.filter(isShown).map { category in
                .init(
                    id: category.category.rawValue,
                    emoji: category.emoji,
                    label: category.label,
                    amount: category.amount,
                    share: category.share,
                    shareText: FinanceMapping.percent(category.share),
                    countText: category.transactions == 1 ? "1 payment" : "\(category.transactions) payments",
                    changeText: category.changePct.flatMap(changeText),
                    area: area(category.category.rawValue)
                )
            }
        )
    }

    /// True when the category shows more than £0 (whole pounds, as `Money.format` shows it).
    static func isShown(_ category: Components.Schemas.CategorySpend) -> Bool {
        category.amount.rounded() > 0
    }

    /// "Up 6% on last month", "Down 13% on last month", "Same as last month".
    static func changeText(_ percent: Double) -> String? {
        let rounded = percent.rounded()
        if rounded > 0 { return L10n.tr("Up \(Int(rounded))% on last month") }
        if rounded < 0 { return L10n.tr("Down \(Int(-rounded))% on last month") }
        return L10n.tr("Same as last month")
    }

    static func subscriptions(_ response: SubscriptionsResponse) -> MoneyWidgetsViewState.Subscriptions {
        let items: [MoneyWidgetsViewState.Subscription] = response.items.map { item in
            let cadence: String = switch item.cadence {
            case .weekly: "a week"
            case .monthly: "a month"
            case .quarterly: "every 3 months"
            case .yearly: "a year"
            }
            return .init(
                id: item.id,
                emoji: item.emoji,
                merchant: item.merchant,
                monthlyCost: item.monthlyCost,
                amountText: "\(FinanceMapping.pounds(item.amount)) \(cadence)",
                nextPaymentText: item.nextPayment.map { date in L10n.tr("Next payment \(FinanceMapping.dayText(date))") },
                priceRiseText: item.priceRise.map {
                    L10n.tr("Price went up from \(FinanceMapping.pounds($0.fromAmount)) to \(FinanceMapping.pounds($0.toAmount)) on \(FinanceMapping.dayText($0.since))")
                },
                priceRiseChip: priceRiseChip(item.priceRise),
                monthlyCostText: FinanceMapping.pounds(item.monthlyCost)
            )
        }
        return .init(
            monthlyTotal: response.monthlyTotal,
            countText: response.count == 1 ? L10n.tr("1 subscription") : L10n.tr("\(response.count) subscriptions"),
            items: items,
            priceRiseCount: items.filter { $0.priceRiseText != nil }.count
        )
    }

    static func bills(_ response: BillsResponse) -> MoneyWidgetsViewState.Bills {
        .init(totalNext30Days: response.totalNext30Days, items: response.items.map(bill))
    }

    static func bill(_ bill: Components.Schemas.Bill) -> MoneyWidgetsViewState.Bill {
        let status: MoneyWidgetsViewState.Bill.Status = switch bill.status {
        case .upcoming: .upcoming
        case .dueSoon: .dueSoon
        case .paid: .paid
        case .overdue: .overdue
        }
        let statusText = switch status {
        case .upcoming: "Upcoming"
        case .dueSoon: "Due soon"
        case .paid: "Paid"
        case .overdue: "Overdue"
        }
        return .init(
            id: bill.id, emoji: bill.emoji, name: bill.name, amount: bill.amount,
            dueText: L10n.tr("Due \(FinanceMapping.dayText(bill.dueDate))"), status: status, statusText: statusText,
            shortDateText: FinanceMapping.shortDateText(bill.dueDate), priceRiseChip: nil
        )
    }

    static func budgets(_ response: BudgetsResponse) -> MoneyWidgetsViewState.Budgets {
        .init(
            monthText: FinanceMapping.monthText(response.month),
            items: response.items.map { budget in
                let status: MoneyWidgetsViewState.Budget.Status = switch budget.status {
                case .ok: .ok
                case .near: .near
                case .over: .over
                }
                let gap = budget.limit - budget.spent
                return .init(
                    id: budget.category.rawValue,
                    emoji: budget.emoji,
                    label: budget.label,
                    limit: budget.limit,
                    spent: budget.spent,
                    progress: budget.progress,
                    status: status,
                    detailText: L10n.tr("\(Money.format(budget.spent)) of \(Money.format(budget.limit))"),
                    statusText: gap < 0 ? L10n.tr("\(Money.format(-gap)) over") : L10n.tr("\(Money.format(gap)) left"),
                    area: area(budget.category.rawValue)
                )
            }
        )
    }

    static func goal(_ goal: SavingsGoal) -> MoneyWidgetsViewState.Goal {
        var planText: String?
        switch (goal.monthlyNeeded, goal.targetDate) {
        case let (monthly?, date?):
            planText = L10n.tr("Save \(Money.format(monthly)) a month to reach it by \(FinanceMapping.dayText(date))")
        case let (nil, date?):
            planText = L10n.tr("Target date \(FinanceMapping.dayText(date))")
        default:
            planText = nil
        }
        return .init(
            id: goal.id, emoji: goal.emoji, name: goal.name, target: goal.target, saved: goal.saved,
            progress: min(1, goal.progress),
            detailText: L10n.tr("\(Money.format(goal.saved)) of \(Money.format(goal.target))"),
            planText: planText
        )
    }
}

/// Budgets and savings goals on Money home show from disk at once, like the other widgets (ADR 0060, 0070).
/// Defined here (feature-local) so the shared `CachedOps` list stays unchanged.
extension CachedOps {
    static let budgets = CachedOp<BudgetsResponse>(key: "getBudgets.now", scope: .user) { try await $0.budgets(month: nil) }
    static let goals = CachedOp<GoalsResponse>(key: "listGoals", scope: .user) { try await $0.goals() }
}
