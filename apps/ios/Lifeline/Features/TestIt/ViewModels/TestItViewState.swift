import Foundation

/// "Test it": every option of one money move, played through the same past period (ADR 0018).
/// Plain values only. Views read this type and never see contract types (ADR 0011).
struct TestItViewState: Equatable, Sendable {
    /// One point on an option's net worth path.
    struct PathPoint: Equatable, Sendable, Identifiable {
        /// "2022-12-31" as sent by the API. Unique within one path.
        var id: String
        var date: Date
        var year: Int
        var netWorth: Double
    }

    /// One option, for example "Fix for 5 years". Every number comes from the API (engine output).
    struct Option: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var isRecommended: Bool
        /// The stored life for this option. "Open in Life" opens it.
        var lifeID: String
        var path: [PathPoint]
        var startNetWorth: Double
        var endNetWorth: Double
        /// End net worth minus the best other option. Positive means this option ended ahead.
        /// Nil when there is only one option.
        var endNetWorthGap: Double?
        /// GBP paid for this option over the period.
        var totalCost: Double
        var missedPayments: Int
        var worstYear: Int
        /// Net worth change in the worst year.
        var worstYearChange: Double
        /// Lifeline Index. 100 is the baseline.
        var index: Double
        /// Plain English lines for VoiceOver and compact layouts, in display order.
        var facts: [String]
        var accessibilitySummary: String
    }

    var phase: LoadPhase
    var title: String
    /// For example "2021-2023 rate shock".
    var periodLabel: String
    /// For example "We played your money through 2021 to 2023."
    var periodSentence: String
    var options: [Option]
    var recommendedID: String?
    /// For example "Fixing for 5 years left you £4,180 better off by 2023."
    var summary: String
    /// For example "7 in 10 twins in similar past periods did better."
    var evidenceSentence: String
    var sources: [SourceChipState]
    /// True when any source is sample data. The View shows the "Sample data" badge.
    var isSampleData: Bool
    /// One y-axis range for every option chart, so the charts compare fairly side by side.
    var chartMin: Double
    var chartMax: Double

    var recommended: Option? { options.first { $0.isRecommended } }
}

/// Closures for `TestItView`. The glue wires them.
struct TestItActions {
    var onRetry: @MainActor () -> Void = {}
    /// Called with the option's `lifeID`.
    var onOpenLife: @MainActor (String) -> Void = { _ in }
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
