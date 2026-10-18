import Foundation
import Testing
import UIKit
@testable import Lifeline

/// Learn course (ADR 0068): path mapping, lesson flow, locked lessons, language, icons.
@MainActor
@Suite("Learn course")
struct LearnTests {
    let course = MockLearnService.Course.bundled
    var order: [String] { course.units.flatMap(\.lessonIds) }

    // MARK: Recorded course

    @Test func recordedCourseHasUnitsAndLessons() {
        #expect((1...8).contains(course.units.count))
        #expect(order.count > 8)
        #expect(course.units.first?.id == "money-basics")
        for entry in course.lessons {
            #expect((2...3).contains(entry.lesson.cards.count))
            #expect(entry.lesson.quiz.count == 3)
            #expect(!entry.lesson.facts.isEmpty)
        }
    }

    /// Every backend icon is an SF Symbol on this OS. The test names any that would fall back.
    @Test func everyBackendIconRenders() {
        let path = MockLearnService.path(course: course, passed: [])
        let missing = LearnMapping.missingSymbols(in: path)
        #expect(missing.isEmpty, "No SF Symbol for: \(missing.joined(separator: ", "))")
    }

    @Test func unknownIconFallsBackToABook() {
        #expect(LearnMapping.symbol("not.a.real.symbol.name") == LearnMapping.fallbackSymbol)
        #expect(UIImage(systemName: LearnMapping.fallbackSymbol) != nil)
        #expect(LearnMapping.symbol("cart") == "cart")
    }

    // MARK: Path mapping

    @Test func pathMapsStatusesProgressAndNextLesson() {
        let passed = Set(order.prefix(4))
        let path = MockLearnService.path(course: course, passed: passed, bonus: [order[6]])
        let state = LearnMapping.pathState(path, phase: .ready, lockedMessage: nil, isSampleData: false)
        let nodes = state.units.flatMap(\.nodes)

        #expect(state.units.count == path.units.count)
        #expect(nodes.count == path.total)
        #expect(nodes.prefix(4).allSatisfy { $0.status == .passed })
        #expect(nodes[4].status == .open)
        #expect(nodes[4].isNext)
        #expect(nodes.dropFirst(5).allSatisfy { $0.status == .locked })
        #expect(state.nextLessonID == order[4])
        #expect(state.progressText == "4 of \(path.total) lessons")
        #expect(state.units[0].eyebrow == "Unit 1")
        let first = path.units[0]
        #expect(state.units[0].progressText == "\(min(4, first.total))/\(first.total)")
        #expect(nodes[6].hasLifeBonus)
        #expect(!nodes[5].hasLifeBonus)
    }

    @Test func lockedNodeCarriesTheServerReason() {
        let path = MockLearnService.path(course: course, passed: Set(order.prefix(1)))
        let state = LearnMapping.pathState(path, phase: .ready, lockedMessage: nil, isSampleData: false)
        let locked = state.units[0].nodes[2]
        let previous = path.units[0].lessons[1].title
        #expect(locked.status == .locked)
        #expect(locked.lockedReason == "Finish \(previous) first")
        #expect(locked.accessibilityLabel.contains("Locked"))
    }

    @Test func nodesWindSideToSide() {
        let path = MockLearnService.path(course: course, passed: [])
        let offsets = LearnMapping.pathState(path, phase: .ready, lockedMessage: nil, isSampleData: false).units[0].nodes.map(\.offset)
        #expect(offsets.first == 0)
        #expect(offsets.contains { $0 > 0 })
        #expect(offsets.contains { $0 < 0 })
        #expect(offsets.allSatisfy { (-1...1).contains($0) })
    }

    @Test func playCardShowsProgressAndNextTitle() {
        let path = MockLearnService.path(course: course, passed: Set(order.prefix(12)))
        let entry = LearnMapping.entry(path)
        let next = LearnMapping.lesson(order[12], in: path)?.title ?? ""
        #expect(entry.progressText == "12 of \(path.total) lessons")
        #expect(entry.nextText == "Next: \(next)")
        #expect(entry.done == 12 && entry.total == path.total)
        #expect(!entry.isLoading)
        #expect(LearnMapping.entry(nil).isLoading)
    }

    @Test func completedCourseHasNoNextLesson() {
        let path = MockLearnService.path(course: course, passed: Set(order))
        #expect(path.nextLessonId == nil)
        #expect(LearnMapping.entry(path).nextText == "Course complete")
    }

    @Test func tapOnLockedLessonShowsReasonAndOpensNothing() async {
        let service = MockLearnService(passedCount: 4)
        let model = LearnPathViewModel(service: service, language: { .en })
        await model.load()
        model.select(order[6])
        #expect(model.openLesson == nil)
        #expect(model.state.lockedMessage?.hasPrefix("Finish ") == true)
        model.select(order[4])
        #expect(model.openLesson?.id == order[4])
        #expect(model.state.lockedMessage == nil)
    }

    @Test func factNumberAndCheckedDate() {
        #expect(LearnMapping.number(in: "You repay 9% of what you earn above £25,000 a year.") == "9%")
        #expect(LearnMapping.number(in: "The allowance is £12,570 a year.") == "£12,570")
        #expect(LearnMapping.number(in: "No number here.") == nil)
        #expect(LearnMapping.checkedText("2026-10-17", language: .en) == "Checked Oct 17, 2026")
    }

    // MARK: Lesson flow

    private func lessonModel(_ service: MockLearnService, id: String, language: AppLanguage = .en) -> LearnLessonViewModel {
        LearnLessonViewModel(lessonID: id, service: service, language: { language })
    }

    private func walkToQuiz(_ model: LearnLessonViewModel) {
        while case .card = model.step { model.next() }
        if model.step == .fact { model.next() }
    }

    @Test func passOpensTheNextLessonAndUpdatesThePath() async {
        let service = MockLearnService(passedCount: 4)
        let path = LearnPathViewModel(service: service, language: { .en })
        await path.load()
        let id = order[4]
        let model = lessonModel(service, id: id)
        var updated: LearnWire.Path?
        model.onPathUpdate = { updated = $0; path.apply($0, language: .en) }
        await model.load()

        #expect(model.phase == .ready)
        #expect(model.step == .card(0))
        #expect(model.state.cards.count >= 2)
        walkToQuiz(model)
        #expect(model.step == .question(0))

        let key = await service.answerKey(id)
        for (index, question) in (model.lesson?.quiz ?? []).enumerated() {
            // Two right, one wrong: still a pass (2 of 3).
            let wrong = question.choices.first { $0.id != key[question.id] }!.id
            model.choose(question: question.id, choice: index == 2 ? wrong : key[question.id]!)
            if index < 2 { model.next() }
        }
        await model.submit()

        let result = model.state.result
        #expect(model.step == .result)
        #expect(result?.passed == true)
        #expect(result?.scoreText == "2 of 3 right")
        #expect(result?.nextLessonID == order[5])
        #expect(model.state.questions.allSatisfy { $0.explanation?.isEmpty == false })
        #expect(model.state.questions[2].isCorrect == false)
        #expect(updated?.done == 5)
        #expect(path.entry.progressText == "5 of \(order.count) lessons")
        #expect(path.state.nextLessonID == order[5])
    }

    @Test func failShowsExplanationsAndRetryPasses() async {
        let service = MockLearnService(passedCount: 4)
        let id = order[4]
        let model = lessonModel(service, id: id)
        await model.load()
        walkToQuiz(model)
        let key = await service.answerKey(id)
        let quiz = model.lesson?.quiz ?? []
        for question in quiz {
            model.choose(question: question.id, choice: question.choices.first { $0.id != key[question.id] }!.id)
            model.next()
        }
        await model.submit()
        #expect(model.state.result?.passed == false)
        #expect(model.state.result?.nextLessonID == nil)
        #expect(model.state.result?.scoreText == "0 of 3 right")
        #expect(model.state.questions.allSatisfy { $0.correctChoiceID != nil && $0.explanation != nil })

        model.tryAgain()
        #expect(model.step == .question(0))
        #expect(model.answers.isEmpty)
        #expect(model.state.result == nil)
        for question in quiz {
            model.choose(question: question.id, choice: key[question.id]!)
            model.next()
        }
        await model.submit()
        #expect(model.state.result?.passed == true)
        #expect(await service.attempts == 2)
    }

    @Test func submitNeedsEveryAnswer() async {
        let service = MockLearnService(passedCount: 4)
        let model = lessonModel(service, id: order[4])
        await model.load()
        walkToQuiz(model)
        #expect(!model.canSubmit)
        model.next()
        #expect(model.step == .question(0), "Next stays on an unanswered question")
        await model.submit()
        #expect(await service.attempts == 0)
    }

    @Test func lockedLessonReports409Reason() async {
        let service = MockLearnService(passedCount: 4)
        let model = lessonModel(service, id: order[8])
        var reason: String?
        model.onLocked = { reason = $0 }
        await model.load()
        let previous = course.lessons.first { $0.lesson.summary.id == order[7] }?.lesson.summary.title ?? ""
        #expect(reason == "Finish \(previous) first")
        guard case let .failed(error) = model.phase else {
            Issue.record("Expected a failed phase")
            return
        }
        #expect(error.title == "This lesson is locked")
        #expect(!error.canRetry)
    }

    @Test func passingAnOldLessonOpensTheNextOpenLesson() async {
        let service = MockLearnService(passedCount: 4)
        let id = order[1]
        let model = lessonModel(service, id: id)
        await model.load()
        walkToQuiz(model)
        let key = await service.answerKey(id)
        for question in model.lesson?.quiz ?? [] {
            model.choose(question: question.id, choice: key[question.id]!)
            model.next()
        }
        await model.submit()
        #expect(model.attempt?.unlockedLessonId == nil)
        #expect(model.state.result?.nextLessonID == order[2])
    }

    // MARK: Language and Penny

    @Test func appLanguageIsSentOnEveryCall() async {
        let service = MockLearnService(passedCount: 4)
        let path = LearnPathViewModel(service: service, language: { .zhHans })
        await path.load()
        let model = lessonModel(service, id: order[4], language: .zhHans)
        await model.load()
        walkToQuiz(model)
        for question in model.lesson?.quiz ?? [] {
            model.choose(question: question.id, choice: question.choices[0].id)
            model.next()
        }
        await model.submit()
        let languages = await service.languages
        #expect(languages == [.zhHans, .zhHans, .zhHans])
    }

    @Test func askPennyCarriesTheLesson() async throws {
        let service = MockLearnService(passedCount: 4)
        let model = lessonModel(service, id: order[4])
        await model.load()
        var context: PennyContext?
        model.onAskPenny = { context = $0 }
        model.actions.onAskPenny()
        let title = model.lesson?.summary.title ?? ""
        #expect(context?.screen == .learnLesson)
        #expect(context?.lessonID == order[4])
        #expect(context?.title == title)
        #expect(context?.question == "Explain this lesson simply")
        let chat = PennyMapping.chatContext(try #require(context), isNewThread: true)
        #expect(chat.screen?.rawValue == "learn_lesson")
        #expect(chat.lessonId == order[4])
        #expect(chat.title == title)
    }

    @Test func mockServiceSelectionForMockClient() {
        let service = LearnServices.make(for: MockClient(data: .recorded))
        #expect(service is MockClient)
    }
}
