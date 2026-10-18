import Foundation

/// "Why?" for a Next Move: the 3 evidence points plus the lesson for the move's concept (ADR 0018).
struct NextMoveWhyViewState: Equatable, Sendable {
    struct Evidence: Equatable, Sendable, Identifiable {
        var id: Int
        /// Plain English. Every number in it comes from the engine's `facts`.
        var text: String
        var source: SourceChipState?
    }

    struct RateBar: Equatable, Sendable, Identifiable {
        var id: String
        /// "5-year fix".
        var label: String
        var value: Double
        /// "4.21%".
        var valueText: String
        /// 0 to 1, relative to the largest rate.
        var fraction: Double
        /// The recommended option's rate (filled bar).
        var isHighlighted: Bool
        /// Bank Rate (dashed bar).
        var isReference: Bool
    }

    struct LessonPreview: Equatable, Sendable {
        var title: String
        /// Always 2 sentences.
        var sentences: [String]
        /// "You spend £47 a month on 6 subscriptions." Nil without finance data.
        var personal: String?
    }

    /// "Fix for 5 years".
    var action: String
    /// "Your deal ends in 165 days".
    var headline: String
    /// "7 in 10 twins in similar past periods did better".
    var confidenceLabel: String
    var evidence: [Evidence]
    var sources: [SourceChipState]
    /// Load state of the lesson only. The evidence shows at once.
    var lessonPhase: LoadPhase
    /// Nil when the concept has no lesson yet.
    var lesson: LessonPreview?
    var isSampleData: Bool
    /// 0 to 1. Penny's face and the confidence chip follow it.
    var confidence: Double = 0
    /// "Medium".
    var confidenceChip: String = ""
    /// Plain English (ADR 0069): "Medium confidence: based on your last 4 weeks of spending". Empty hides it.
    var confidenceText: String = ""
    /// "Worst past period: £310 a year worse off".
    var worstCaseText: String = ""
    /// Rate bars taken from the evidence facts (keys ending in `_pct`).
    var rates: [RateBar] = []
    /// All sources on one line, grouped: "Bank of England · live, Your bank · sample".
    var ratesSourceText: String?
    /// Mortgage moves also link to the full Real-life Decision screen (W7).
    var hasDecisionDetail: Bool = false
    /// Opening lines (ADR 0050): one sentence per key source, then one combining sentence. Empty hides them.
    var sourceSentences: [String] = []
    /// "What you give up" summary (ADR 0042). Nil hides the section.
    var tradeOffSummary: String? = nil
    /// Every trade-off point, shown like the evidence.
    var tradeOff: [Evidence] = []
}

struct NextMoveWhyActions {
    /// Opens the full lesson (chart and quiz).
    var onOpenLesson: @MainActor () -> Void = {}
    /// Opens the full Real-life Decision (mortgage moves only).
    var onOpenDecision: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}
    /// "Ask Penny a follow-up". Nil hides the button.
    var onAskPenny: (@MainActor () -> Void)?

    static var noop: Self { .init() }
}
