import Foundation
import Observation

/// One Learn lesson (ADR 0068): cards one at a time, the real number, a 3-question quiz graded by the server.
@MainActor
@Observable
final class LearnLessonViewModel {
    typealias Step = LearnLessonViewState.Step

    let lessonID: String
    let fallbackTitle: String
    let unitTitle: String?
    let isSampleData: Bool
    private let service: any LearnService
    private let client: (any LifelineClient)?
    private let language: @MainActor () -> AppLanguage
    private(set) var lesson: LearnWire.Lesson?
    private(set) var phase: LoadPhase = .loading(.init(message: L10n.tr("Loading the lesson")))
    private(set) var step: Step = .card(0)
    private(set) var answers: [String: String] = [:]
    private(set) var attempt: LearnWire.AttemptResult?
    private(set) var isSubmitting = false
    private(set) var errorText: String?

    /// The server refused the lesson (409 `lesson_locked`). The glue shows the reason on the path and closes.
    @ObservationIgnored var onLocked: @MainActor (String) -> Void = { _ in }
    /// Each graded attempt carries the whole path.
    @ObservationIgnored var onPathUpdate: @MainActor (LearnWire.Path) -> Void = { _ in }
    @ObservationIgnored var onNextLesson: @MainActor (String) -> Void = { _ in }
    @ObservationIgnored var onAskPenny: @MainActor (PennyContext) -> Void = { _ in }
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(
        lessonID: String,
        title: String = "",
        unitTitle: String? = nil,
        service: any LearnService,
        client: (any LifelineClient)? = nil,
        isSampleData: Bool = false,
        language: @escaping @MainActor () -> AppLanguage = { .current }
    ) {
        self.lessonID = lessonID
        self.fallbackTitle = title
        self.unitTitle = unitTitle
        self.service = service
        self.client = client
        self.isSampleData = isSampleData
        self.language = language
    }

    var state: LearnLessonViewState {
        LearnMapping.lessonState(
            lessonID: lessonID, fallbackTitle: fallbackTitle, lesson: lesson, unitTitle: unitTitle, phase: phase,
            step: step, answers: answers, attempt: attempt, isSubmitting: isSubmitting, errorText: errorText,
            isSampleData: isSampleData
        )
    }

    var actions: LearnLessonActions {
        LearnLessonActions(
            onNext: { [weak self] in self?.next() },
            onBack: { [weak self] in self?.back() },
            onChoose: { [weak self] question, choice in self?.choose(question: question, choice: choice) },
            onSubmit: { [weak self] in Task { await self?.submit() } },
            onTryAgain: { [weak self] in self?.tryAgain() },
            onNextLesson: { [weak self] id in self?.onNextLesson(id) },
            onAskPenny: { [weak self] in
                guard let self else { return }
                self.onAskPenny(self.pennyContext)
            },
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    /// "Ask Penny about this lesson": the server loads the lesson from `lesson_id`.
    var pennyContext: PennyContext {
        let title = lesson?.summary.title ?? fallbackTitle
        return PennyContext(screen: .learnLesson, question: L10n.tr("Explain this lesson simply"), title: title, lessonID: lessonID)
    }

    // MARK: Loading

    /// Disk first (lesson text is fixed), then network. A 409 means the lesson is locked.
    func load() async {
        if lesson == nil { phase = .loading(.init(message: L10n.tr("Loading the lesson"))) }
        let language = language()
        do {
            let op = LearnCache.lesson(service, id: lessonID, language: language)
            if let client {
                try await client.load(op) { [weak self] value in self?.show(value) }
            } else {
                show(try await service.learnLesson(id: lessonID, language: language))
            }
        } catch {
            handle(APIError.map(error))
        }
    }

    private func show(_ value: LearnWire.Lesson) {
        let first = lesson == nil
        lesson = value
        phase = .ready
        if first { step = steps.first ?? .card(0) }
    }

    private func handle(_ error: APIError) {
        if case let .server(_, code, message, _) = error, code == LearnWire.lockedCode {
            let reason = message.isEmpty ? LearnMapping.lockedFallback(previous: nil) : message
            phase = .failed(.init(title: L10n.tr("This lesson is locked"), message: reason, canRetry: false))
            onLocked(reason)
            return
        }
        if lesson == nil { phase = .failed(.from(error)) } else { errorText = error.userMessage }
    }

    // MARK: Steps

    private var steps: [Step] { state.steps }

    func next() {
        let all = steps
        guard let index = all.firstIndex(of: step) else { return }
        if case let .question(q) = step {
            guard let quiz = lesson?.quiz, quiz.indices.contains(q), answers[quiz[q].id] != nil else { return }
        }
        if index + 1 < all.count { step = all[index + 1] }
    }

    func back() {
        let all = steps
        guard step != .result, let index = all.firstIndex(of: step), index > 0 else { return }
        step = all[index - 1]
    }

    func choose(question: String, choice: String) {
        guard attempt == nil, !isSubmitting else { return }
        answers[question] = choice
    }

    /// True on the last question once every question has an answer.
    var canSubmit: Bool {
        guard let quiz = lesson?.quiz, !quiz.isEmpty else { return false }
        return quiz.allSatisfy { answers[$0.id] != nil }
    }

    /// The server grades. The response carries the explanations and the new path.
    func submit() async {
        guard canSubmit, !isSubmitting, attempt == nil else { return }
        isSubmitting = true
        errorText = nil
        defer { isSubmitting = false }
        do {
            let result = try await service.attemptLearnLesson(id: lessonID, answers: answers, language: language())
            attempt = result
            step = .result
            onPathUpdate(result.path)
        } catch {
            handle(APIError.map(error))
        }
    }

    /// Clears the answers and starts the quiz again. The cards stay one tap back.
    func tryAgain() {
        attempt = nil
        answers = [:]
        errorText = nil
        step = steps.first { if case .question = $0 { true } else { false } } ?? .card(0)
    }
}
