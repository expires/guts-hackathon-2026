import Foundation

/// Learn fixtures for previews and the Playground (ADR 0068). Built from the recorded course, so the text,
/// icons and numbers match the server.
@MainActor
enum LearnFixtures {
    static var course: MockLearnService.Course { .bundled }
    static var order: [String] { course.units.flatMap(\.lessonIds) }

    /// A sample student: the first 4 lessons passed, a Life bonus star on 2 later lessons.
    static var samplePath: LearnWire.Path {
        let passed = Set(order.prefix(4))
        let bonus = Set(order.dropFirst(4).filter { id in course.lessons.first { $0.lesson.summary.id == id }?.lesson.summary.conceptId != nil }.prefix(2))
        return MockLearnService.path(course: course, passed: passed, bonus: bonus)
    }

    static var entry: LearnEntryState { LearnMapping.entry(samplePath) }

    static var path: LearnPathViewState {
        LearnMapping.pathState(samplePath, phase: .ready, lockedMessage: nil, isSampleData: true)
    }

    /// After a tap on a locked lesson.
    static var pathLocked: LearnPathViewState {
        var state = path
        let locked = state.units.flatMap(\.nodes).first { $0.status == .locked }
        state.lockedMessage = locked?.lockedReason
        return state
    }

    static var pathLoading: LearnPathViewState {
        LearnMapping.pathState(nil, phase: .loading(.init(message: "Loading your lessons")), lockedMessage: nil, isSampleData: false)
    }

    static var pathError: LearnPathViewState {
        LearnMapping.pathState(nil, phase: .failed(.from(.network)), lockedMessage: nil, isSampleData: false)
    }

    // MARK: Lesson

    /// The first open lesson of the sample student.
    static var openEntry: MockLearnService.Entry {
        let id = order.count > 4 ? order[4] : order[0]
        return course.lessons.first { $0.lesson.summary.id == id } ?? course.lessons[0]
    }

    static func lesson(
        step: LearnLessonViewState.Step, answers: [String: String] = [:], attempt: LearnWire.AttemptResult? = nil
    ) -> LearnLessonViewState {
        var lesson = openEntry.lesson
        lesson.summary.status = .open
        return LearnMapping.lessonState(
            lessonID: lesson.summary.id, fallbackTitle: lesson.summary.title, lesson: lesson,
            unitTitle: course.units.first { $0.lessonIds.contains(lesson.summary.id) }?.title,
            phase: .ready, step: step, answers: answers, attempt: attempt, isSubmitting: false, errorText: nil,
            isSampleData: true
        )
    }

    static var lessonCard: LearnLessonViewState { lesson(step: .card(0)) }
    static var lessonFact: LearnLessonViewState { lesson(step: .fact) }

    static var lessonQuestion: LearnLessonViewState {
        let first = openEntry.lesson.quiz[0]
        return lesson(step: .question(0), answers: [first.id: first.choices[0].id])
    }

    /// `rightCount` of 3 answers right.
    static func attempt(rightCount: Int) -> (answers: [String: String], result: LearnWire.AttemptResult) {
        let entry = openEntry
        var answers: [String: String] = [:]
        var results: [LearnWire.AnswerResult] = []
        for (index, key) in entry.answers.enumerated() {
            let question = entry.lesson.quiz.first { $0.id == key.questionId }
            let wrong = question?.choices.first { $0.id != key.correctChoiceId }?.id ?? "z"
            let right = index < rightCount
            answers[key.questionId] = right ? key.correctChoiceId : wrong
            results.append(.init(questionId: key.questionId, correct: right, correctChoiceId: key.correctChoiceId, explanation: key.explanation))
        }
        let passed = rightCount >= 2
        var done = Set(order.prefix(4))
        if passed { done.insert(entry.lesson.summary.id) }
        let path = MockLearnService.path(course: course, passed: done)
        let unlocked = passed ? order.first { !done.contains($0) } : nil
        return (answers, .init(passed: passed, correct: rightCount, passMark: 2, results: results, unlockedLessonId: unlocked, path: path))
    }

    static var resultPass: LearnLessonViewState {
        let (answers, result) = attempt(rightCount: 2)
        return lesson(step: .result, answers: answers, attempt: result)
    }

    static var resultFail: LearnLessonViewState {
        let (answers, result) = attempt(rightCount: 1)
        return lesson(step: .result, answers: answers, attempt: result)
    }

    static var lessonLocked: LearnLessonViewState {
        var state = lessonCard
        state.phase = .failed(.init(title: "This lesson is locked", message: "Finish Make a budget first", canRetry: false))
        return state
    }

    static var lessonLoading: LearnLessonViewState {
        var state = lessonCard
        state.phase = .loading(.init(message: "Loading the lesson"))
        state.cards = []
        state.facts = []
        state.questions = []
        return state
    }
}
