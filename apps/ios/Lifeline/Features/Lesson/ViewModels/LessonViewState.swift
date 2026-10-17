import Foundation

struct LessonViewState: Equatable, Sendable {
    struct Quiz: Equatable, Sendable {
        var question: String
        var options: [String]
        var answerIndex: Int
        /// Nil until the player taps an option.
        var selectedIndex: Int?

        var isAnswered: Bool { selectedIndex != nil }
        var isCorrect: Bool { selectedIndex == answerIndex }
    }

    var conceptID: String
    var title: String
    var chart: ChartState
    /// Always exactly 2 sentences.
    var sentences: [String]
    var quiz: Quiz
    /// True when this lesson unlocked a new concept.
    var isNewConcept: Bool
    /// One sentence with the player's real numbers (`Lesson.personal`, ADR 0016),
    /// for example "You spend £47 a month on 6 subscriptions." Nil without finance data.
    var personal: String? = nil
    /// "2008 · Age 26". Nil when the lesson opens outside a life (Money tab, concept list).
    var eyebrow: String? = nil
    /// First and last chart value, for example "3.2% → 4.1%" or "£695 → £1,150". Nil with fewer than 2 points.
    var heroLine: String? = nil
    /// Words after the hero line: the chart title.
    var heroCaption: String = ""
    /// For example "Up 0.9 points from 2006 to 2008." Derived from the chart.
    var changeSentence: String? = nil
    /// For example "New concept · Prices creep up · 3 learned".
    var conceptLine: String = ""
    /// True when the glue wired "Rewind and try again" and the life has a decision to rewind.
    var canRewind: Bool = false
    /// True when the client returns canned data. The View shows "Mock data".
    var isSampleData: Bool = false
}

struct LessonActions {
    var onAnswer: @MainActor (Int) -> Void = { _ in }
    var onClose: @MainActor () -> Void = {}
    var onRewind: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
