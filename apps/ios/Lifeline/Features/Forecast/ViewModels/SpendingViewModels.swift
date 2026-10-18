import Foundation
import Observation

/// One category in "Where your money goes" and "All spending" (B3.2, B3.5).
struct SpendingSlice: Equatable, Sendable, Identifiable {
    /// Contract category, e.g. "groceries".
    var id: String
    var label: String
    var amount: Double
    /// "£96".
    var amountText: String
    /// 0 to 1 of the shown spending.
    var share: Double
    /// "36%".
    var shareText: String
    /// "£14 less than Sep", "Same as Sep". Nil when unknown.
    var changeText: String?
    /// Colour by rank: 0 green, 1 blue, 2 orange, 3 purple, 4 grey, then light grey.
    var colorIndex: Int
}

/// Spending for one month: day-to-day categories in the pie, rent and bills apart.
struct SpendingPieState: Equatable, Sendable {
    /// "2026-10".
    var month: String
    /// "October 2026".
    var monthTitle: String
    /// "October so far" or "September".
    var periodText: String
    /// "1 to 18 Oct · so far" or "Whole month".
    var rangeText: String
    /// True for the month that is still running.
    var isCurrent: Bool
    var total: Double
    /// "£268".
    var totalText: String
    /// "so far" or "in total", under the total in the pie.
    var centerCaption: String
    /// Day-to-day categories, largest first, £0 hidden.
    var slices: [SpendingSlice]
    /// Rent, bills and subscriptions, listed apart.
    var fixed: [SpendingSlice]

    /// The 5 largest categories for Money home.
    var top: [SpendingSlice] { Array(slices.prefix(5)) }

    /// Categories never in "spending": money moving between your own pots, or coming in.
    static let ignored: Set<String> = ["transfers", "income", "savings"]
    /// Rent and bills: shown apart (they are in the forecast as bills).
    static let fixedCategories: Set<String> = ["housing", "bills", "subscriptions"]

    /// - Parameter previous: the month before, for "£14 less than Sep". Nil falls back to `change_pct`.
    static func make(_ response: SpendingResponse, previous: SpendingResponse? = nil) -> SpendingPieState {
        let asOf = String(response.meta.asOf.prefix(10))
        let isCurrent = asOf.hasPrefix(response.month) && asOf != ForecastMock.addDays(-1, to: ForecastMock.addMonths(1, to: response.month) + "-01")
        let shown = response.categories.filter { $0.amount.rounded() > 0 && !ignored.contains($0.category.rawValue) }
        let day = shown.filter { !fixedCategories.contains($0.category.rawValue) }.sorted { $0.amount > $1.amount }
        let fixed = shown.filter { fixedCategories.contains($0.category.rawValue) }.sorted { $0.amount > $1.amount }
        let total = day.reduce(0) { $0 + $1.amount }
        let previousName = previous.map { ForecastText.shortMonth($0.month) }
        func slice(_ category: Components.Schemas.CategorySpend, index: Int, base: Double) -> SpendingSlice {
            let share = base > 0 ? category.amount / base : 0
            var change: String?
            if let previous, let previousName {
                let before = previous.categories.first { $0.category == category.category }?.amount ?? 0
                let diff = category.amount.rounded() - before.rounded()
                change = diff > 0 ? L10n.tr("\(ForecastText.whole(diff)) more than \(previousName)")
                    : diff < 0 ? L10n.tr("\(ForecastText.whole(-diff)) less than \(previousName)")
                    : L10n.tr("Same as \(previousName)")
            } else {
                change = category.changePct.map { percent in
                    let rounded = Int(percent.rounded())
                    return rounded > 0 ? L10n.tr("Up \(rounded)% on last month")
                        : rounded < 0 ? L10n.tr("Down \(-rounded)% on last month") : L10n.tr("Same as last month")
                }
            }
            return SpendingSlice(
                id: category.category.rawValue, label: category.label, amount: category.amount,
                amountText: ForecastText.whole(category.amount), share: share, shareText: FinanceMapping.percent(share),
                changeText: change, colorIndex: index
            )
        }
        let monthName = ForecastText.monthName(response.month)
        let rangeText: String = {
            guard isCurrent, let date = FinanceMapping.date(asOf) else { return L10n.tr("Whole month") }
            let dayNumber = FinanceMapping.format(date, template: "d")
            return L10n.tr("1 to \(dayNumber) \(ForecastText.shortMonth(response.month)) · so far")
        }()
        return SpendingPieState(
            month: response.month,
            monthTitle: FinanceMapping.monthText(response.month),
            periodText: isCurrent ? L10n.tr("\(monthName) so far") : monthName,
            rangeText: rangeText,
            isCurrent: isCurrent,
            total: total,
            totalText: ForecastText.whole(total),
            centerCaption: isCurrent ? L10n.tr("so far") : L10n.tr("in total"),
            slices: day.enumerated().map { slice($1, index: $0, base: total) },
            fixed: fixed.enumerated().map { slice($1, index: 5, base: max(total, 1)) }.map { var s = $0; s.shareText = ""; return s }
        )
    }
}

// MARK: - All spending

struct AllSpendingState: Equatable, Sendable {
    var phase: LoadPhase = .loading(.standard)
    var pie: SpendingPieState?
    var canGoBack = false
    var canGoForward = false
    /// "Not counted here: rent £540 and bills. Those are in "Due before 2 November"."
    var fixedNote: String?
}

struct AllSpendingActions {
    var onBack: @MainActor () -> Void = {}
    var onPrevious: @MainActor () -> Void = {}
    var onNext: @MainActor () -> Void = {}
    var onCategory: @MainActor (String) -> Void = { _ in }
    var onRetry: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// "All spending": month switch through every statement month, the pie, every category and its change.
@MainActor
@Observable
final class AllSpendingViewModel {
    private let client: any LifelineClient
    /// Every statement month, oldest first (`SpendingResponse.months`).
    private(set) var months: [String] = []
    /// The month shown. Nil means this month.
    private(set) var month: String?
    private var responses: [String: SpendingResponse] = [:]
    private var phase: LoadPhase = .loading(.standard)
    private var currentMonth: String?

    @ObservationIgnored var onBack: @MainActor () -> Void = {}
    @ObservationIgnored var onCategory: @MainActor (_ category: String, _ month: String?) -> Void = { _, _ in }

    init(client: any LifelineClient) {
        self.client = client
    }

    private var shownMonth: String? { month ?? currentMonth }

    var state: AllSpendingState {
        var state = AllSpendingState(phase: phase)
        guard let shown = shownMonth, let response = responses[shown] else { return state }
        let previous = index(of: shown).flatMap { $0 > 0 ? responses[months[$0 - 1]] : nil }
        let pie = SpendingPieState.make(response, previous: previous)
        state.pie = pie
        state.phase = .ready
        if let index = index(of: shown) {
            state.canGoBack = index > 0
            state.canGoForward = index < months.count - 1
        }
        if !pie.fixed.isEmpty {
            let parts = pie.fixed.map { "\($0.label.lowercased()) \($0.amountText)" }.joined(separator: ", ")
            state.fixedNote = L10n.tr("Not counted in the pie: \(parts). Penny counts rent and bills apart.")
        }
        return state
    }

    var actions: AllSpendingActions {
        AllSpendingActions(
            onBack: { [weak self] in self?.onBack() },
            onPrevious: { [weak self] in self?.step(-1) },
            onNext: { [weak self] in self?.step(1) },
            onCategory: { [weak self] category in
                guard let self else { return }
                onCategory(category, shownMonth == currentMonth ? nil : shownMonth)
            },
            onRetry: { [weak self] in Task { await self?.load() } }
        )
    }

    private func index(of month: String) -> Int? { months.firstIndex(of: month) }

    /// This month first (cached at once), then the month before it for the change text.
    func load() async {
        await show(nil)
    }

    func step(_ delta: Int) {
        guard let shown = shownMonth, let index = index(of: shown), months.indices.contains(index + delta) else { return }
        let target = months[index + delta]
        Task { await show(target == currentMonth ? nil : target) }
    }

    func show(_ target: String?) async {
        month = target
        if let target, responses[target] == nil { phase = .loading(.standard) }
        do {
            try await client.load(CachedOps.spending(month: target)) { [weak self] response in
                guard let self else { return }
                if target == nil { currentMonth = response.month }
                if let list = response.months, !list.isEmpty { months = list }
                if !months.contains(response.month) { months.append(response.month) }
                responses[response.month] = response
                phase = .ready
            }
        } catch {
            if responses[shownMonth ?? ""] == nil { phase = .failed(.from(APIError.map(error))) }
            return
        }
        // The month before, for "£14 less than Sep".
        if let shown = shownMonth, let index = index(of: shown), index > 0 {
            let before = months[index - 1]
            if responses[before] == nil {
                try? await client.load(CachedOps.spending(month: before)) { [weak self] in self?.responses[before] = $0 }
            }
        }
    }
}

// MARK: - Category

struct CategoryDetailState: Equatable, Sendable {
    struct Bar: Equatable, Sendable, Identifiable {
        var id: Int
        /// "£36".
        var amountText: String
        /// 0 to 1 of the largest week.
        var fraction: Double
        /// "1–7 Oct" or "15–18 Oct so far".
        var label: String
    }

    struct Payment: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        /// "16 Oct".
        var dateText: String
        /// "£14.20".
        var amountText: String
    }

    var phase: LoadPhase = .loading(.standard)
    var title: String
    /// "£96".
    var totalText: String = ""
    /// "in October so far".
    var periodText: String = ""
    /// "You usually spend about £110 a month here."
    var usualText: String?
    var bars: [Bar] = []
    var payments: [Payment] = []
    /// "Ask Penny about groceries".
    var askTitle: String = ""

    static func make(_ detail: CategoryDetail, currentMonth: Bool) -> CategoryDetailState {
        let monthName = ForecastText.monthName(detail.month)
        let largest = detail.weeks.map(\.amount).max() ?? 0
        let asOf = String(detail.meta.asOf.prefix(10))
        return CategoryDetailState(
            phase: .ready,
            title: detail.label,
            totalText: ForecastText.whole(detail.total),
            periodText: currentMonth ? L10n.tr("in \(monthName) so far") : L10n.tr("in \(monthName)"),
            usualText: detail.usualMonthly > 0 ? L10n.tr("You usually spend about \(ForecastText.whole(detail.usualMonthly)) a month here.") : nil,
            bars: detail.weeks.enumerated().map { index, week in
                let start = FinanceMapping.date(week.start).map { FinanceMapping.format($0, template: "d") } ?? week.start
                var label = "\(start)–\(ForecastText.shortDate(week.end))"
                if currentMonth, week.end >= asOf { label = L10n.tr("\(label) so far") }
                return Bar(id: index, amountText: ForecastText.whole(week.amount), fraction: largest > 0 ? week.amount / largest : 0, label: label)
            },
            payments: detail.transactions.sorted { $0.date > $1.date }.map { transaction in
                Payment(
                    id: transaction.id,
                    name: transaction.merchant.flatMap { $0.isEmpty ? nil : $0 } ?? transaction.description,
                    dateText: ForecastText.shortDate(transaction.date),
                    amountText: ForecastText.pence(abs(transaction.amount))
                )
            },
            askTitle: L10n.tr("Ask Penny about \(detail.label.lowercased())")
        )
    }
}

struct CategoryDetailActions {
    var onBack: @MainActor () -> Void = {}
    var onAskPenny: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// One category: total, usual monthly amount, bars by week, every payment, Ask Penny about it.
@MainActor
@Observable
final class CategoryDetailViewModel {
    private let client: any LifelineClient
    let category: String
    let month: String?
    private let label: String
    private(set) var detail: CategoryDetail?
    private var phase: LoadPhase = .loading(.standard)

    @ObservationIgnored var onBack: @MainActor () -> Void = {}
    @ObservationIgnored var onAskPenny: @MainActor (_ label: String) -> Void = { _ in }

    /// - Parameter month: YYYY-MM, or nil for this month.
    init(client: any LifelineClient, category: String, label: String, month: String?) {
        self.client = client
        self.category = category
        self.label = label
        self.month = month
    }

    static func op(category: String, month: String?) -> CachedOp<CategoryDetail> {
        CachedOp(key: "getCategoryDetail.\(category).\(month ?? "now")", scope: .user) {
            try await $0.categoryDetail(category: category, month: month)
        }
    }

    var state: CategoryDetailState {
        guard let detail else { return CategoryDetailState(phase: phase, title: label) }
        return CategoryDetailState.make(detail, currentMonth: month == nil)
    }

    var actions: CategoryDetailActions {
        CategoryDetailActions(
            onBack: { [weak self] in self?.onBack() },
            onAskPenny: { [weak self] in
                guard let self else { return }
                onAskPenny(detail?.label ?? label)
            },
            onRetry: { [weak self] in Task { await self?.load() } }
        )
    }

    func load() async {
        if detail == nil { phase = .loading(.standard) }
        do {
            try await client.load(Self.op(category: category, month: month)) { [weak self] in
                self?.detail = $0
                self?.phase = .ready
            }
        } catch {
            if detail == nil { phase = .failed(.from(APIError.map(error))) }
        }
    }
}
