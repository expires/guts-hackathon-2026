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

    func load() async {
        overview = nil; spending = nil; subscriptions = nil; bills = nil; budgets = nil; goals = nil
        let client = self.client
        async let overview = Self.result { try await client.financeOverview() }
        async let spending = Self.result { try await client.financeSpending(month: nil) }
        async let subscriptions = Self.result { try await client.subscriptions() }
        async let bills = Self.result { try await client.bills() }
        async let budgets = Self.result { try await client.budgets(month: nil) }
        async let goals = Self.result { try await client.goals() }
        self.overview = await overview
        self.spending = await spending
        self.subscriptions = await subscriptions
        self.bills = await bills
        self.budgets = await budgets
        self.goals = await goals
    }

    private nonisolated static func result<T: Sendable>(_ body: @Sendable () async throws -> T) async -> Result<T, APIError> {
        do { return .success(try await body()) } catch { return .failure(APIError.map(error)) }
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

    static func moveLink(for widget: Widget, moves: [Move]) -> MoveLinkState? {
        for kind in widget.moveKinds {
            if let move = moves.first(where: { $0.kind.rawValue == kind }) {
                let impact = move.impactPerYear.rounded()
                let suffix = impact > 0 ? " (\(Money.format(impact)) a year)" : ""
                return MoveLinkState(moveID: move.id, text: "Your next move: \(move.action)\(suffix)")
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
        return MoneyWidgetsViewState(
            overview: section(overview, link: moveLink(for: .overview, moves: moves), map: Self.overview),
            spending: section(spending, link: moveLink(for: .spending, moves: moves), map: Self.spending),
            subscriptions: section(subscriptions, link: moveLink(for: .subscriptions, moves: moves), map: Self.subscriptions),
            bills: section(bills, link: moveLink(for: .bills, moves: moves), map: Self.bills),
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
        return .init(
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
            asOfText: "As of " + FinanceMapping.dayText(response.meta.asOf)
        )
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
            categories: response.categories.map { category in
                .init(
                    id: category.category.rawValue,
                    emoji: category.emoji,
                    label: category.label,
                    amount: category.amount,
                    share: category.share,
                    shareText: FinanceMapping.percent(category.share),
                    countText: category.transactions == 1 ? "1 payment" : "\(category.transactions) payments",
                    changeText: category.changePct.flatMap(changeText)
                )
            }
        )
    }

    /// "Up 6% on last month", "Down 13% on last month", "Same as last month".
    static func changeText(_ percent: Double) -> String? {
        let rounded = percent.rounded()
        if rounded > 0 { return "Up \(Int(rounded))% on last month" }
        if rounded < 0 { return "Down \(Int(-rounded))% on last month" }
        return "Same as last month"
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
                nextPaymentText: item.nextPayment.map { "Next payment " + FinanceMapping.dayText($0) },
                priceRiseText: item.priceRise.map {
                    "Price went up from \(FinanceMapping.pounds($0.fromAmount)) to \(FinanceMapping.pounds($0.toAmount)) on \(FinanceMapping.dayText($0.since))"
                }
            )
        }
        return .init(
            monthlyTotal: response.monthlyTotal,
            countText: response.count == 1 ? "1 subscription" : "\(response.count) subscriptions",
            items: items,
            priceRiseCount: items.filter { $0.priceRiseText != nil }.count
        )
    }

    static func bills(_ response: BillsResponse) -> MoneyWidgetsViewState.Bills {
        .init(
            totalNext30Days: response.totalNext30Days,
            items: response.items.map { bill in
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
                    dueText: "Due " + FinanceMapping.dayText(bill.dueDate), status: status, statusText: statusText
                )
            }
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
                    detailText: "\(Money.format(budget.spent)) of \(Money.format(budget.limit))",
                    statusText: gap < 0 ? "\(Money.format(-gap)) over" : "\(Money.format(gap)) left"
                )
            }
        )
    }

    static func goal(_ goal: SavingsGoal) -> MoneyWidgetsViewState.Goal {
        var planText: String?
        switch (goal.monthlyNeeded, goal.targetDate) {
        case let (monthly?, date?):
            planText = "Save \(Money.format(monthly)) a month to reach it by \(FinanceMapping.dayText(date))"
        case let (nil, date?):
            planText = "Target date \(FinanceMapping.dayText(date))"
        default:
            planText = nil
        }
        return .init(
            id: goal.id, emoji: goal.emoji, name: goal.name, target: goal.target, saved: goal.saved,
            progress: min(1, goal.progress),
            detailText: "\(Money.format(goal.saved)) of \(Money.format(goal.target))",
            planText: planText
        )
    }
}
