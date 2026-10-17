import Foundation
import Observation

/// Full-screen lesson: chart, 2 sentences, 1-tap quiz. Never paywalled.
@MainActor
@Observable
final class LessonViewModel {
    private let lesson: Lesson
    private let isNewConcept: Bool
    private(set) var selectedIndex: Int?
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(lesson: Lesson, isNewConcept: Bool) {
        self.lesson = lesson
        self.isNewConcept = isNewConcept
    }

    var state: LessonViewState {
        Self.makeState(lesson: lesson, isNewConcept: isNewConcept, selectedIndex: selectedIndex)
    }

    var actions: LessonActions {
        LessonActions(
            onAnswer: { [weak self] index in
                guard let self, selectedIndex == nil, lesson.quiz.options.indices.contains(index) else { return }
                selectedIndex = index
            },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    static func makeState(lesson: Lesson, isNewConcept: Bool, selectedIndex: Int?) -> LessonViewState {
        LessonViewState(
            conceptID: lesson.conceptId,
            title: lesson.title,
            chart: StateMapping.chart(lesson.chart),
            sentences: lesson.sentences,
            quiz: .init(
                question: lesson.quiz.question,
                options: lesson.quiz.options,
                answerIndex: lesson.quiz.answerIndex,
                selectedIndex: selectedIndex
            ),
            isNewConcept: isNewConcept,
            personal: lesson.personal
        )
    }
}
