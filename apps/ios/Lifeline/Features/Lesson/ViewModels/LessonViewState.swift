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
}

struct LessonActions {
    var onAnswer: @MainActor (Int) -> Void = { _ in }
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
