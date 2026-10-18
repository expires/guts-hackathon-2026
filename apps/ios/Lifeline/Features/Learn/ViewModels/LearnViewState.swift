import Foundation

// Learn course (ADR 0068): plain view states. No generated contract types here (ADR 0011).

/// Status of one lesson on the path.
enum LearnNodeStatus: String, Equatable, Sendable {
    case passed, open, locked
}

/// The "Learn" card on the Play tab.
struct LearnEntryState: Equatable, Sendable {
    /// "12 of 57 lessons".
    var progressText: String
    /// 0 to 1.
    var progress: Double
    var done: Int = 0
    var total: Int = 0
    /// "Next: Make a budget". Nil when every lesson is passed or the path is not loaded yet.
    var nextText: String?
    var isLoading: Bool

    static let loading = LearnEntryState(progressText: "", progress: 0, nextText: nil, isLoading: true)
}

/// The course path: six units, each a winding line of lesson nodes.
struct LearnPathViewState: Equatable, Sendable {
    struct Node: Equatable, Sendable, Identifiable {
        var id: String
        var title: String
        /// SF Symbol name that exists on this device (the server's `icon`, else a generic book).
        var symbol: String
        var status: LearnNodeStatus
        /// Server text for a locked lesson. Always nil since PENNY_V3_BUILD E1 (no locks).
        var lockedReason: String?
        /// The concept was also earned in a Life game.
        var hasLifeBonus: Bool
        /// The first open lesson: the path scrolls to it.
        var isNext: Bool
        /// Sideways position on the winding path, -1 (left) to 1 (right).
        var offset: Double
        /// "Make a budget. Lesson 3 of 8. Locked. Finish Needs and wants first."
        var accessibilityLabel: String
    }

    struct UnitSection: Equatable, Sendable, Identifiable {
        var id: String
        /// "Unit 1".
        var eyebrow: String
        var title: String
        var description: String
        /// "3/8".
        var progressText: String
        /// "3 of 8 lessons done".
        var progressLabel: String
        var progress: Double
        var nodes: [Node]
    }

    var phase: LoadPhase
    var units: [UnitSection]
    /// "12 of 57 lessons".
    var progressText: String
    var progress: Double
    var nextLessonID: String?
    /// Shown after a tap on a locked lesson, for example "Finish Needs and wants first".
    var lockedMessage: String?
    var isSampleData: Bool

    static let empty = LearnPathViewState(
        phase: .loading(.init(message: "Loading")), units: [], progressText: "", progress: 0,
        nextLessonID: nil, lockedMessage: nil, isSampleData: false
    )
}

struct LearnPathActions {
    var onSelect: @MainActor (String) -> Void = { _ in }
    var onDismissLocked: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// One lesson: cards, the real number, a 3-question quiz, then the result.
struct LearnLessonViewState: Equatable, Sendable {
    enum Step: Equatable, Sendable, Hashable {
        case card(Int)
        case fact
        case question(Int)
        case result
    }

    struct Card: Equatable, Sendable, Identifiable {
        var id: Int
        var title: String
        var text: String
    }

    struct Fact: Equatable, Sendable, Identifiable {
        var id: Int
        /// The number from the text, for example "£25,000" or "9%". Nil when the text has none.
        var number: String?
        var text: String
        var sourceLabel: String
        var sourceURL: URL?
        /// "Checked 17 Oct 2026".
        var checkedText: String
        /// "Why this matters to you: ..." (PENNY_V3_BUILD E3). Nil hides the line.
        var whyText: String? = nil
    }

    struct Choice: Equatable, Sendable, Identifiable {
        var id: String
        var text: String
    }

    struct Question: Equatable, Sendable, Identifiable {
        var id: String
        var text: String
        var choices: [Choice]
        var selectedChoiceID: String?
        /// After grading.
        var isCorrect: Bool?
        var correctChoiceID: String?
        var explanation: String?
    }

    struct Result: Equatable, Sendable {
        var passed: Bool
        /// "2 of 3 right".
        var scoreText: String
        /// "Lesson passed!" or "Not this time".
        var headline: String
        /// "You need 2 of 3 to pass. Read why below, then try again."
        var detail: String
        /// The lesson "Next lesson" opens. Nil hides the button.
        var nextLessonID: String?
        /// "Next: Make a budget".
        var nextText: String?
    }

    var phase: LoadPhase
    var lessonID: String
    var title: String
    var symbol: String
    /// "Money basics".
    var unitTitle: String?
    var cards: [Card]
    var facts: [Fact]
    var questions: [Question]
    var step: Step
    var result: Result?
    var isSubmitting: Bool
    var errorText: String?
    var isSampleData: Bool

    /// Every step in order: cards, the fact page, then one page per question. The result is not counted.
    var steps: [Step] {
        cards.indices.map(Step.card) + (facts.isEmpty ? [] : [.fact]) + questions.indices.map(Step.question)
    }

    /// Position of `step` in `steps`, from 0. The result counts as the end.
    var stepIndex: Int {
        steps.firstIndex(of: step) ?? steps.count
    }

    var currentQuestion: Question? {
        if case let .question(index) = step, questions.indices.contains(index) { return questions[index] }
        return nil
    }

    /// Progress bar segments (PENNY_V3_BUILD E4): one per card, plus one for the quiz.
    var progressSegments: Int {
        cards.count + (questions.isEmpty ? 0 : 1)
    }

    /// Segments filled for `step`: card 2 of 3 fills 2; the real number fills every card; the quiz and the
    /// result fill the quiz segment too.
    var filledSegments: Int {
        switch step {
        case let .card(index): min(index + 1, cards.count)
        case .fact: cards.count
        case .question, .result: progressSegments
        }
    }

    /// "Card 1 of 2", "The real number", "Question 2 of 3", "Result".
    var stepLabel: String {
        switch step {
        case let .card(index): L10n.tr("Card \(index + 1) of \(cards.count)")
        case .fact: L10n.tr("The real number")
        case let .question(index): L10n.tr("Question \(index + 1) of \(questions.count)")
        case .result: L10n.tr("Result")
        }
    }
}

struct LearnLessonActions {
    var onNext: @MainActor () -> Void = {}
    var onBack: @MainActor () -> Void = {}
    var onChoose: @MainActor (_ questionID: String, _ choiceID: String) -> Void = { _, _ in }
    var onSubmit: @MainActor () -> Void = {}
    var onTryAgain: @MainActor () -> Void = {}
    var onNextLesson: @MainActor (String) -> Void = { _ in }
    var onAskPenny: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
