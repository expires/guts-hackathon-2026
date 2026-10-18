import Foundation
import Observation

/// Ask Penny (ADR 0031, amendment "perceived speed"). Streams one turn at a time:
/// reaction, real tool steps, verified bubbles with a typing pause, done. Falls back to `POST /v1/chat`
/// when the stream fails. Every bubble on screen came from a `bubble` event or a final response.
@MainActor
@Observable
final class PennyViewModel {
    static var verifyingLabel: String { L10n.tr("Checking the numbers…") }
    nonisolated static var introText: String { L10n.tr("Ask me about your money, or anything about student life. When I use your numbers, I check every one.") }
    nonisolated static var onboardingIntroText: String { L10n.tr("Hi, I'm Penny. Ask me anything about student money. I can't see your numbers yet.") }
    /// Starter chips in onboarding: student money in general, no personal data needed.
    nonisolated static var onboardingChips: [String] { [
        L10n.tr("How does the maintenance loan work?"),
        L10n.tr("How do I make a weekly budget?"),
        L10n.tr("Is an overdraft a good idea?"),
    ] }
    /// Starter chips for students (Ask Penny context fix).
    nonisolated static var chips: [String] { [
        L10n.tr("Can I afford a night out this week?"),
        L10n.tr("How long will my money last?"),
        L10n.tr("Is a Lifetime ISA worth it for me?"),
        L10n.tr("How do I make a weekly budget?"),
    ] }
    /// No event (keepalive included) for this long ends the stream and starts the fallback.
    static let defaultStreamIdleTimeout: Duration = .seconds(20)

    /// One of Penny's answers to a question: still streaming, or final.
    enum Answer: Equatable, Sendable {
        case streaming(id: String, bubbles: [Components.Schemas.BubbleEvent])
        case final(PennyAPI.Response)

        var id: String {
            switch self {
            case let .streaming(id, _): id
            case let .final(response): response.messageId
            }
        }
    }

    enum Status: Equatable, Sendable {
        case working(step: String?)
        case done
        case failed(ErrorViewState)
    }

    /// One user message and the answers attached to it.
    struct Exchange: Equatable, Sendable {
        /// Local id until the server sends `reply_to`, then the server's message id.
        var id: String
        var text: String
        var reaction: PennyReaction?
        /// The thread root's id for a reply asked inside a thread. Nil for a top-level question.
        var rootID: String?
        var answers: [Answer] = []
        var status: Status
        /// `ChatMessage.replies` from a loaded thread.
        var serverReplies = 0
    }

    /// Where the newest question came from. `ask(_:)` replaces it (Penny tab, ADR 0051).
    private(set) var context: PennyContext
    /// True in the Penny tab: no close button.
    var isTab = false
    /// A context question that arrived while Penny was busy. Sent when the turn ends.
    private var pendingQuestion: String?
    private let service: PennyService
    private(set) var exchanges: [Exchange] = []
    private(set) var threadID: String?
    private(set) var pastThreads: [PennyViewState.ThreadSummary] = []
    private(set) var openThreadQuestionID: String?
    private(set) var openHighlightID: String?
    private(set) var expandedSources: Set<String> = []
    /// Presentation mode (ADR 0029): money amounts are rounded. The glue sets it from `llPresentationMode`.
    var presentation = false
    private var localCounter = 0
    private var turn: Task<Void, Never>?
    private var didStart = false

    @ObservationIgnored var onClose: @MainActor () -> Void = {}
    @ObservationIgnored var onOpenLink: @MainActor (PennyLink) -> Void = { _ in }

    private let streamIdleTimeout: Duration

    init(service: PennyService, context: PennyContext = .init(), streamIdleTimeout: Duration = PennyViewModel.defaultStreamIdleTimeout) {
        self.service = service
        self.context = context
        self.streamIdleTimeout = streamIdleTimeout
    }

    /// Onboarding chat (ADR 0063): no data, no Next Move links, no past chats.
    var isOnboarding: Bool { context.screen == .onboarding }

    var isWorking: Bool {
        exchanges.contains { if case .working = $0.status { true } else { false } }
    }

    // MARK: State

    var state: PennyViewState {
        let now = service.now()
        let rows = openThreadQuestionID.map { threadRows(rootID: $0, now: now) } ?? mainRows(now: now)
        let lastConfidence = exchanges.last.flatMap { exchange -> Double? in
            guard case let .final(response)? = exchange.answers.last else { return nil }
            return response.confidence
        }
        let canReply = openThreadQuestionID.map { !$0.hasPrefix("local-") } ?? true
        let faceRow = rows.last { if case .question = $0 { false } else { true } }
        let suggestionsGroup: String? = {
            guard !isWorking, case let .answer(group)? = rows.last, group.isComplete, !group.suggestions.isEmpty else { return nil }
            return group.id
        }()
        var state = PennyViewState(
            title: openThreadQuestionID == nil ? (isTab ? "Penny" : L10n.tr("Ask Penny")) : L10n.tr("Thread"),
            openThreadQuestionID: openThreadQuestionID,
            rows: rows,
            chips: exchanges.isEmpty && openThreadQuestionID == nil ? (isOnboarding ? Self.onboardingChips : Self.chips) : [],
            pastThreads: exchanges.isEmpty ? pastThreads : [],
            isWorking: isWorking,
            canSend: !isWorking && canReply,
            pennyMood: isWorking ? .thinking : (lastConfidence.map(PennyMood.from(confidence:)) ?? .smiling),
            openHighlightID: openHighlightID,
            expandedSourceGroups: expandedSources,
            isPresentation: presentation,
            inputPlaceholder: openThreadQuestionID == nil ? L10n.tr("Ask Penny anything") : L10n.tr("Reply in this thread")
        )
        state.showsClose = !isTab
        if isOnboarding {
            state.introText = Self.onboardingIntroText
            state.pastThreads = []
            // No Next Move or plan links: there is no data to link to yet.
            state.rows = state.rows.map { row in
                guard case var .answer(group) = row else { return row }
                group.links = []
                return .answer(group)
            }
        }
        state.pennyFaceRowID = faceRow?.id
        state.suggestionsGroupID = suggestionsGroup
        return state
    }

    private func mainRows(now: Date) -> [PennyViewState.Row] {
        exchanges.filter { $0.rootID == nil }.flatMap { exchange in
            var rows: [PennyViewState.Row] = [.question(question(exchange))]
            if let first = exchange.answers.first { rows.append(.answer(group(first, now: now))) }
            rows.append(contentsOf: statusRows(exchange))
            return rows
        }
    }

    private func threadRows(rootID: String, now: Date) -> [PennyViewState.Row] {
        exchanges.filter { $0.id == rootID || $0.rootID == rootID }.flatMap { exchange in
            var rows: [PennyViewState.Row] = [.question(question(exchange, inThread: true))]
            rows.append(contentsOf: exchange.answers.map { .answer(group($0, now: now)) })
            rows.append(contentsOf: statusRows(exchange))
            return rows
        }
    }

    private func statusRows(_ exchange: Exchange) -> [PennyViewState.Row] {
        switch exchange.status {
        case let .working(step): [.working(id: exchange.id, step: step)]
        case let .failed(error): [.failed(id: exchange.id, error: error)]
        case .done: []
        }
    }

    private func question(_ exchange: Exchange, inThread: Bool = false) -> PennyViewState.Question {
        .init(
            id: exchange.id,
            text: exchange.text,
            reaction: exchange.reaction,
            replyCount: inThread || exchange.rootID != nil ? 0 : replyCount(rootID: exchange.id, server: exchange.serverReplies),
            isReply: exchange.rootID != nil
        )
    }

    /// Penny's answer groups in the thread of `rootID` (the root's own answers included).
    func replyCount(rootID: String, server: Int = 0) -> Int {
        let local = exchanges.filter { $0.id == rootID || $0.rootID == rootID }.reduce(0) { $0 + $1.answers.count }
        return max(local, server)
    }

    private func group(_ answer: Answer, now: Date) -> PennyViewState.AnswerGroup {
        switch answer {
        case let .final(response):
            return PennyMapping.answerGroup(response, presentation: presentation, now: now)
        case let .streaming(id, events):
            var bubbles: [PennyViewState.Bubble] = []
            for event in events {
                let (bubble, _) = PennyMapping.bubble(
                    event.bubble, highlights: event.highlights ?? [], facts: [], sources: [],
                    groupID: id, presentation: presentation, now: now
                )
                bubbles.append(bubble)
            }
            return .init(
                id: id, bubbles: bubbles, highlights: [:], confidence: 0.5, links: [], sourceGroups: [],
                sourcesTitle: "", disclaimer: "", isVerified: true, isComplete: false
            )
        }
    }

    // MARK: Actions

    var actions: PennyActions {
        PennyActions(
            onSend: { [weak self] text in self?.send(text) },
            onChip: { [weak self] text in self?.send(text) },
            onOpenThread: { [weak self] id in self?.openThread(id) },
            onCloseThread: { [weak self] in self?.closeThread() },
            onTapHighlight: { [weak self] id in self?.toggleHighlight(id) },
            onToggleSources: { [weak self] id in self?.toggleSources(id) },
            onLink: { [weak self] link in self?.onOpenLink(link) },
            onOpenPastThread: { [weak self] id in self?.loadThread(id: id) },
            onRetry: { [weak self] id in self?.retry(exchangeID: id) },
            onClose: { [weak self] in
                guard let self, !isTab else { return }
                turn?.cancel()
                onClose()
            }
        )
    }

    /// First appearance: sends the context question, if any, and loads past chats for an empty chat.
    func start() async {
        guard !didStart else { return }
        didStart = true
        if let question = context.question?.trimmingCharacters(in: .whitespacesAndNewlines), !question.isEmpty {
            send(question)
            return
        }
        guard !isOnboarding else { return }
        try? await service.loadThreads { [weak self] threads in
            self?.pastThreads = PennyMapping.pastThreads(threads)
        }
    }

    /// Sends a question. Inside an open thread it replies to the thread's root question.
    func send(_ raw: String) {
        let text = String(raw.trimmingCharacters(in: .whitespacesAndNewlines).prefix(2_000))
        guard !text.isEmpty, !isWorking else { return }
        let rootID = openThreadQuestionID
        if let rootID, rootID.hasPrefix("local-") { return }
        localCounter += 1
        let exchange = Exchange(id: "local-\(localCounter)", text: text, rootID: rootID, status: .working(step: nil))
        exchanges.append(exchange)
        openHighlightID = nil
        startTurn(exchangeID: exchange.id)
    }

    /// Waits for the running turn. Tests and the Playground use it.
    func waitForTurn() async {
        await turn?.value
    }

    func openThread(_ questionID: String) {
        openThreadQuestionID = questionID
        openHighlightID = nil
    }

    func closeThread() {
        openThreadQuestionID = nil
        openHighlightID = nil
    }

    func toggleHighlight(_ id: String) {
        openHighlightID = openHighlightID == id ? nil : id
    }

    func toggleSources(_ groupID: String) {
        if expandedSources.contains(groupID) { expandedSources.remove(groupID) } else { expandedSources.insert(groupID) }
    }

    func retry(exchangeID: String) {
        guard !isWorking, let index = exchanges.firstIndex(where: { $0.id == exchangeID }) else { return }
        exchanges[index].answers = []
        exchanges[index].status = .working(step: nil)
        startTurn(exchangeID: exchangeID)
    }

    /// Opens an earlier chat (`GET /v1/chat/threads/{id}`).
    func loadThread(id: String) {
        guard !isWorking else { return }
        turn = Task { [weak self] in
            guard let self else { return }
            do {
                let thread = try await service.getThread(id)
                apply(thread: thread)
            } catch is CancellationError {
                return
            } catch {
                pastThreads = []
            }
        }
    }

    func apply(thread: PennyAPI.Thread) {
        threadID = thread.id
        var built: [Exchange] = []
        func root(of id: String?) -> String? {
            guard let id, let parent = built.first(where: { $0.id == id }) else { return nil }
            return parent.rootID ?? parent.id
        }
        for message in thread.messages {
            if message.role.rawValue == "user" {
                built.append(Exchange(
                    id: message.id, text: message.text ?? "", rootID: root(of: message.replyTo),
                    status: .done, serverReplies: message.replies ?? 0
                ))
            } else if let response = message.response,
                      let index = built.firstIndex(where: { $0.id == (message.replyTo ?? response.replyTo) }) {
                built[index].answers.append(.final(response))
                built[index].reaction = built[index].reaction ?? PennyMapping.reaction(response.reaction.rawValue)
            }
        }
        exchanges = built
        openThreadQuestionID = nil
    }

    // MARK: Streaming turn

    private func startTurn(exchangeID: String) {
        turn = Task { [weak self] in
            await self?.runTurn(exchangeID: exchangeID)
            self?.sendPendingQuestion()
        }
    }

    /// "Ask Penny" from another screen (Penny tab). With a question: starts a NEW chat with this context
    /// (the running turn stops) and sends the question at once, so Penny starts answering.
    /// Without a question (the Penny icon): keeps the chat and only updates the context.
    func ask(_ newContext: PennyContext) {
        didStart = true
        context = newContext
        closeThread()
        guard let question = newContext.question?.trimmingCharacters(in: .whitespacesAndNewlines), !question.isEmpty else { return }
        startNewChat()
        send(question)
    }

    /// Clears the chat on screen. The next request has no `thread_id`, so the server opens a new thread
    /// titled from `context.threadTitle`.
    func startNewChat() {
        turn?.cancel()
        turn = nil
        pendingQuestion = nil
        exchanges = []
        threadID = nil
        openHighlightID = nil
        expandedSources = []
        openThreadQuestionID = nil
    }

    private func sendPendingQuestion() {
        guard let question = pendingQuestion, !isWorking else { return }
        pendingQuestion = nil
        send(question)
    }

    func request(for exchange: Exchange) -> PennyAPI.Request {
        let replyTo = exchange.rootID.flatMap { $0.hasPrefix("local-") ? nil : $0 }
        return PennyAPI.Request(
            message: exchange.text,
            threadId: threadID,
            replyTo: replyTo,
            context: PennyMapping.chatContext(context, isNewThread: threadID == nil)
        )
    }

    private func runTurn(exchangeID: String) async {
        guard let exchange = exchanges.first(where: { $0.id == exchangeID }) else { return }
        let request = request(for: exchange)
        let streamID = "stream-\(exchangeID)"
        var currentID = exchangeID
        var lastSeq = -1
        var finished = false
        do {
            for try await event in Self.withIdleTimeout(service.stream(request), timeout: streamIdleTimeout) {
                try Task.checkCancellation()
                guard event.seq > lastSeq else { continue }
                lastSeq = event.seq
                switch event._type.rawValue {
                case "reaction":
                    update(currentID) { $0.reaction = PennyMapping.reaction(event.reaction?.rawValue) ?? $0.reaction }
                case "tool_step":
                    if let label = event.step?.label { update(currentID) { $0.status = .working(step: label) } }
                case "verifying":
                    update(currentID) { $0.status = .working(step: Self.verifyingLabel) }
                case "bubble":
                    guard let bubble = event.bubble, !bubble.bubble.text.isEmpty else { continue }
                    try await service.sleep(Self.typingPause(for: bubble.bubble.text))
                    appendStreamed(bubble, streamID: streamID, to: currentID)
                case "done":
                    guard let response = event.response else { continue }
                    currentID = try await finish(exchangeID: currentID, response: response)
                    finished = true
                default:
                    // "keepalive": the idle timer already restarted when it arrived.
                    // "error": `done` with the template summary follows.
                    continue
                }
                if finished { break }
            }
        } catch is CancellationError {
            return
        } catch {
            // Stream failed. Fall through to the non-streaming endpoint.
        }
        if Task.isCancelled || finished { return }
        do {
            let response = try await service.ask(request)
            _ = try await finish(exchangeID: currentID, response: response)
        } catch is CancellationError {
            return
        } catch {
            update(currentID) {
                $0.answers.removeAll { if case .streaming = $0 { true } else { false } }
                $0.status = .failed(Self.unavailableError)
            }
        }
    }

    private func appendStreamed(_ bubble: Components.Schemas.BubbleEvent, streamID: String, to exchangeID: String) {
        update(exchangeID) { exchange in
            if let index = exchange.answers.firstIndex(where: { $0.id == streamID }),
               case let .streaming(id, bubbles) = exchange.answers[index] {
                guard !bubbles.contains(where: { $0.bubble.id == bubble.bubble.id }) else { return }
                exchange.answers[index] = .streaming(id: id, bubbles: bubbles + [bubble])
            } else {
                exchange.answers.append(.streaming(id: streamID, bubbles: [bubble]))
            }
        }
    }

    /// Shows the bubbles the stream did not send yet (with typing pauses), then replaces the streamed
    /// group with the final response. The final response decides what stays on screen.
    /// Returns the exchange's new id (the server's user message id).
    private func finish(exchangeID: String, response: PennyAPI.Response) async throws -> String {
        let streamID = "stream-\(exchangeID)"
        let shown = Set(exchanges.first { $0.id == exchangeID }?.answers.flatMap { answer -> [String] in
            guard case let .streaming(id, bubbles) = answer, id == streamID else { return [] }
            return bubbles.map(\.bubble.id)
        } ?? [])
        for bubble in response.bubbles where !shown.contains(bubble.id) {
            try await service.sleep(Self.typingPause(for: bubble.text))
            let highlights = (response.highlights ?? []).filter { $0.bubbleId == bubble.id }
            appendStreamed(.init(bubble: bubble, highlights: highlights), streamID: streamID, to: exchangeID)
        }
        try Task.checkCancellation()
        threadID = response.threadId
        let newID = response.replyTo.isEmpty ? exchangeID : response.replyTo
        update(exchangeID) { exchange in
            exchange.answers.removeAll { $0.id == streamID || $0.id == response.messageId }
            exchange.answers.append(.final(response))
            exchange.reaction = exchange.reaction ?? PennyMapping.reaction(response.reaction.rawValue)
            exchange.status = .done
        }
        rename(exchangeID, to: newID)
        return newID
    }

    private func rename(_ old: String, to new: String) {
        guard old != new else { return }
        for index in exchanges.indices {
            if exchanges[index].id == old { exchanges[index].id = new }
            if exchanges[index].rootID == old { exchanges[index].rootID = new }
        }
        if openThreadQuestionID == old { openThreadQuestionID = new }
    }

    private func update(_ id: String, _ change: (inout Exchange) -> Void) {
        guard let index = exchanges.firstIndex(where: { $0.id == id }) else { return }
        change(&exchanges[index])
    }

    /// One calm message for every chat failure (DIRECTION_V2 section 6, fix 9).
    static var unavailableError: ErrorViewState { ErrorViewState(title: PennyMapping.unavailable, message: "", canRetry: true) }

    struct StreamIdleTimeout: Error {}

    /// Forwards `upstream` and fails with `StreamIdleTimeout` when no event (keepalive included) arrives
    /// for `timeout`. Each event restarts the timer.
    nonisolated static func withIdleTimeout<Element: Sendable>(
        _ upstream: AsyncThrowingStream<Element, any Error>,
        timeout: Duration
    ) -> AsyncThrowingStream<Element, any Error> {
        AsyncThrowingStream { continuation in
            let clock = ContinuousClock()
            let last = LastEvent(clock.now)
            let reader = Task {
                do {
                    for try await element in upstream {
                        await last.touch(clock.now)
                        continuation.yield(element)
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            let watchdog = Task {
                let tick = timeout / 4
                while !Task.isCancelled {
                    try? await Task.sleep(for: tick)
                    if await clock.now - last.value >= timeout {
                        continuation.finish(throwing: StreamIdleTimeout())
                        reader.cancel()
                        return
                    }
                }
            }
            continuation.onTermination = { _ in
                reader.cancel()
                watchdog.cancel()
            }
        }
    }

    private actor LastEvent {
        var value: ContinuousClock.Instant
        init(_ value: ContinuousClock.Instant) { self.value = value }
        func touch(_ now: ContinuousClock.Instant) { value = now }
    }

    /// 400 ms for a short bubble, up to 700 ms for 240 characters or more.
    nonisolated static func typingPause(for text: String) -> Duration {
        let share = min(Double(text.count), 240) / 240
        return .milliseconds(400 + Int((300 * share).rounded()))
    }
}
