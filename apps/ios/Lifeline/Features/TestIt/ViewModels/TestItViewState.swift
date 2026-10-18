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
        /// One row per path year after the first, for the story column. Derived from `path` and the character's birth year.
        var yearRows: [YearRow] = []
        /// "Paid from 2021 to 2023".
        var costLabel: String = ""
        /// "Index 104.2".
        var indexLabel: String = ""
    }

    /// One year in an option's story column, for example "2022 · Age 30" / "I have £71,200." / "Up £5,200".
    struct YearRow: Equatable, Sendable, Identifiable {
        var id: String
        var title: String
        var text: String
        /// Change against the year before, for example "Up £5,200". Nil on the first row.
        var change: String?
        var isDown: Bool
    }

    /// Hero under the cards: recommended option against the cheapest other option, plus the API summary.
    /// Nil when there is only one option or no recommended option.
    struct Hero: Equatable, Sendable {
        var amount: Double
        var amountText: String
        /// For example "more paid than \"Fix for 2 years\"".
        var caption: String
        /// The API `summary`, verbatim.
        var text: String
    }

    var phase: LoadPhase
    var title: String
    /// For example "2021-2023 rate shock".
    var periodLabel: String
    /// For example "We played your money through 2021 to 2023."
    var periodSentence: String
    var options: [Option]
    var recommendedID: String?
    /// The API `summary`, verbatim. For example "In the 2021-2023 rate shock (stress test), “Take a tracker” cost £7,280 more than “Fix for 2 years”."
    var summary: String
    /// For example "7 in 10 twins in similar past periods did better."
    var evidenceSentence: String
    var sources: [SourceChipState]
    /// True when any source is sample data. The View shows the "Sample data" badge.
    var isSampleData: Bool
    /// One y-axis range for every option chart, so the charts compare fairly side by side.
    var chartMin: Double
    var chartMax: Double
    /// "Two of you. Same life. One choice is different."
    var intro: String = ""
    /// Face icon key for the option cards (character emoji from the API).
    var faceEmoji: String? = nil
    var hero: Hero? = nil
    /// True when the glue wired "Do this" (add the move to the plan).
    var canDoThis: Bool = false

    var recommended: Option? { options.first { $0.isRecommended } }
}

/// Closures for `TestItView`. The glue wires them.
struct TestItActions {
    var onRetry: @MainActor () -> Void = {}
    /// Called with the option's `lifeID`.
    var onOpenLife: @MainActor (String) -> Void = { _ in }
    var onClose: @MainActor () -> Void = {}
    /// "Do this": add the move to the plan.
    var onDoThis: @MainActor () -> Void = {}
    /// "Ask Penny what this means". Nil hides the button.
    var onAskPenny: (@MainActor () -> Void)? = nil

    static var noop: Self { .init() }
}
