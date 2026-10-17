import Foundation

/// Insights screen: what stands out, income against spending, where the money goes, top shops,
/// subscriptions, unusual payments and spending patterns. Plain values only.
struct InsightsViewState: Equatable, Sendable {
    struct MonthBar: Equatable, Sendable, Identifiable {
        var id: String
        /// "Sep".
        var label: String
        var income: Double
        var spend: Double
        /// "Sep: earned £2,480, spent £1,865".
        var spokenText: String
    }

    struct CategoryRow: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var emoji: String
        /// Life area colour name, see `MoneyWidgetsViewModel.area`.
        var area: String
        var share: Double
        var amountText: String
        /// "24% of spending".
        var detailText: String
        /// "Up 12%" or "Down 8%". Nil when there is no earlier period to compare with.
        var changeText: String?
        var changeIsUp: Bool
        var trend: [Double]
    }

    struct MerchantRow: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var emoji: String
        /// "21 payments".
        var detailText: String
        var amountText: String
    }

    struct SubscriptionRow: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var emoji: String
        /// "£155.88 a year".
        var annualText: String
        /// "£12.99".
        var monthlyText: String
    }

    struct UnusualRow: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var emoji: String
        /// "18 Jul. Usually about £32.50 for Shopping."
        var detailText: String
        var amountText: String
    }

    struct WeekdayBar: Equatable, Sendable, Identifiable {
        var id: String
        /// "Mon".
        var label: String
        var amount: Double
        var isBiggest: Bool
    }

    struct Patterns: Equatable, Sendable {
        /// 0 to 1. Nil when there is no treat spending.
        var weekendShare: Double?
        var weekendText: String?
        var averageDailyText: String
        var biggestDayText: String?
        var biggestWeekdayText: String?
        var weekdays: [WeekdayBar]
    }

    var phase: LoadPhase
    /// What the user asked for: 3, 6 or 12.
    var selectedMonths: Int
    /// "Based on your last 3 months". Nil when the full window exists.
    var note: String?
    /// "June to September 2026".
    var windowText: String
    /// The short factual sentences at the top.
    var sentences: [String]
    var months: [MonthBar]
    var earnedText: String
    var spentText: String
    var categories: [CategoryRow]
    var merchants: [MerchantRow]
    var subscriptionsMonthlyText: String
    var subscriptionsAnnualText: String
    var subscriptions: [SubscriptionRow]
    var unusual: [UnusualRow]
    var patterns: Patterns?
    /// True when there are fewer than 2 complete months, so nothing can be shown yet.
    var hasNoHistory: Bool
    var isSampleData: Bool

    static let windowOptions = [3, 6, 12]
}

struct InsightsActions {
    var onSelectMonths: @MainActor (Int) -> Void = { _ in }
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// The Money tab card that opens Insights: last full month at a glance plus the top sentences.
struct InsightsTeaserState: Equatable, Sendable {
    /// "September".
    var monthText: String
    var spentText: String
    var earnedText: String
    /// Share of the month's income that was spent, 0 to 1. Nil without income.
    var spentShare: Double?
    /// Up to 2 sentences.
    var sentences: [String]
    var isSampleData: Bool
}
