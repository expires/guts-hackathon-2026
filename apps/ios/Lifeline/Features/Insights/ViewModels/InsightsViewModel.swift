import Foundation
import Observation

/// Loads `GET /v1/finance/insights?months=N`. Sentences, labels and the window note come from the backend.
@MainActor
@Observable
final class InsightsViewModel {
    static let loadingMessage = "Looking at your spending"

    private let client: any LifelineClient
    private(set) var insights: SpendingInsights?
    private(set) var phase: LoadPhase = .loading(.init(message: InsightsViewModel.loadingMessage))
    private(set) var selectedMonths: Int
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(client: any LifelineClient, months: Int = 6) {
        self.client = client
        selectedMonths = months
    }

    var state: InsightsViewState {
        Self.makeState(insights: insights, months: selectedMonths, phase: phase)
    }

    var actions: InsightsActions {
        InsightsActions(
            onSelectMonths: { [weak self] in self?.select(months: $0) },
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    func select(months: Int) {
        guard months != selectedMonths else { return }
        selectedMonths = months
        Task { await load() }
    }

    func load() async {
        // Keep the old numbers on screen while a new window loads, so the page does not jump.
        if insights == nil { phase = .loading(.init(message: Self.loadingMessage)) }
        let months = selectedMonths
        do {
            let result = try await client.insights(months: months)
            guard months == selectedMonths else { return }
            insights = result
            phase = .ready
        } catch {
            guard months == selectedMonths else { return }
            phase = .failed(.from(APIError.map(error)))
        }
    }

    // MARK: Pure mapping (used by fixtures, the Money tab card and tests)

    static let weekdayShort = ["Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed", "Thursday": "Thu",
                               "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun"]

    static func makeState(insights: SpendingInsights?, months: Int, phase: LoadPhase) -> InsightsViewState {
        guard let insights else {
            return InsightsViewState(
                phase: phase, selectedMonths: months, note: nil, windowText: "", sentences: [], months: [],
                earnedText: "", spentText: "", categories: [], merchants: [], subscriptionsMonthlyText: "",
                subscriptionsAnnualText: "", subscriptions: [], unusual: [], patterns: nil, hasNoHistory: false,
                isSampleData: true
            )
        }
        let monthBars = insights.monthly.map { item -> InsightsViewState.MonthBar in
            let name = FinanceMapping.shortMonthText(item.month + "-01")
            return .init(
                id: item.month, label: name, income: item.income, spend: item.spend,
                spokenText: "\(name): earned \(Money.format(item.income)), spent \(Money.format(item.spend))"
            )
        }
        let trends = Dictionary(uniqueKeysWithValues: insights.categoryByMonth.map { ($0.category.rawValue, $0.values) })
        let categories = insights.categories.prefix(8).map { item -> InsightsViewState.CategoryRow in
            let change = item.changePct
            return .init(
                id: item.category.rawValue, label: item.label, emoji: item.emoji,
                area: MoneyWidgetsViewModel.area(item.category.rawValue), share: item.share,
                amountText: Money.format(item.amount),
                detailText: "\(FinanceMapping.percent(item.share)) of spending",
                changeText: change.flatMap { abs($0) >= 1 ? "\($0 > 0 ? "Up" : "Down") \(Int(abs($0).rounded()))%" : nil },
                changeIsUp: (change ?? 0) > 0,
                trend: trends[item.category.rawValue] ?? []
            )
        }
        let merchants = insights.topMerchants.map { item -> InsightsViewState.MerchantRow in
            .init(
                id: item.merchant + item.category.rawValue, name: item.merchant, emoji: item.emoji,
                detailText: item.count == 1 ? "1 payment" : "\(item.count) payments",
                amountText: Money.format(item.amount)
            )
        }
        let subs = insights.subscriptions.items.map { item -> InsightsViewState.SubscriptionRow in
            .init(
                id: item.merchant, name: item.merchant, emoji: item.emoji,
                annualText: "\(FinanceMapping.pounds(item.annualCost)) a year",
                monthlyText: FinanceMapping.pounds(item.monthlyCost)
            )
        }
        let labelFor = Dictionary(uniqueKeysWithValues: insights.categories.map { ($0.category.rawValue, $0.label) })
        let unusual = insights.unusual.map { item -> InsightsViewState.UnusualRow in
            let kind = labelFor[item.category.rawValue] ?? "this type"
            return .init(
                id: item.id, name: item.merchant, emoji: item.emoji,
                detailText: "\(FinanceMapping.shortDateText(item.date)). Usually about \(Money.format(item.typical)) for \(kind.lowercased()).",
                amountText: Money.format(item.amount)
            )
        }
        let p = insights.patterns
        let biggest = p.byWeekday.map(\.amount).max() ?? 0
        let patterns = InsightsViewState.Patterns(
            weekendShare: p.weekendShare,
            weekendText: p.weekendShare.map { "\(FinanceMapping.percent($0)) of treat spending is at weekends" },
            averageDailyText: "\(FinanceMapping.pounds(p.averageDailySpend)) a day on average",
            biggestDayText: p.biggestDay.flatMap { day in
                p.biggestDayAmount.map { "\(FinanceMapping.shortDayText(day)): \(Money.format($0))" }
            },
            biggestWeekdayText: p.biggestWeekday.map { "\($0)s are your biggest spending day" },
            weekdays: p.byWeekday.map {
                .init(id: $0.weekday, label: weekdayShort[$0.weekday] ?? $0.weekday, amount: $0.amount, isBiggest: $0.amount == biggest && biggest > 0)
            }
        )
        let hasNoHistory = insights.windowMonths < 2
        return InsightsViewState(
            phase: phase,
            selectedMonths: months,
            note: insights.note,
            windowText: windowText(start: insights.startMonth, end: insights.endMonth),
            sentences: insights.insights,
            months: monthBars,
            earnedText: Money.format(insights.totalIncome),
            spentText: Money.format(insights.totalSpend),
            categories: Array(categories),
            merchants: merchants,
            subscriptionsMonthlyText: FinanceMapping.pounds(insights.subscriptions.monthlyTotal),
            subscriptionsAnnualText: FinanceMapping.pounds(insights.subscriptions.annualTotal),
            subscriptions: subs,
            unusual: unusual,
            patterns: hasNoHistory ? nil : patterns,
            hasNoHistory: hasNoHistory,
            isSampleData: FinanceMapping.isSample(insights.meta)
        )
    }

    /// "June to September 2026". One month: "September 2026".
    static func windowText(start: String?, end: String?) -> String {
        guard let start, let end else { return "" }
        if start == end { return FinanceMapping.monthText(end) }
        let from = FinanceMapping.format(FinanceMapping.date(start + "-01") ?? Date(), template: start.prefix(4) == end.prefix(4) ? "MMMM" : "MMMMyyyy")
        return "\(from) to \(FinanceMapping.monthText(end))"
    }

    /// The Money tab card. Nil when there is nothing to say yet.
    static func teaser(_ insights: SpendingInsights?) -> InsightsTeaserState? {
        guard let insights, insights.windowMonths >= 2, let last = insights.monthly.last else { return nil }
        let sentences = Array(insights.insights.prefix(2))
        guard !sentences.isEmpty else { return nil }
        return InsightsTeaserState(
            monthText: FinanceMapping.format(FinanceMapping.date(last.month + "-01") ?? Date(), template: "MMMM"),
            spentText: Money.format(last.spend),
            earnedText: Money.format(last.income),
            spentShare: last.income > 0 ? last.spend / last.income : nil,
            sentences: sentences,
            isSampleData: FinanceMapping.isSample(insights.meta)
        )
    }
}
