import Foundation

/// Ask Penny fixtures (W7). Contract values come from the `ChatAnswer` example shape in
/// `contracts/openapi.yaml`. Previews, the Playground and tests use them.
@MainActor
enum PennyFixtures {
    /// Pinned clock: 5 minutes after the sources' `updated_at`.
    static let now = PennyMapping.parseDate("2026-10-17T12:05:00Z") ?? Date()

    // MARK: Contract values

    static let answerJSON = """
    {"thread_id":"th_1","message_id":"msg_2","reply_to":"msg_1","reaction":"brain",
     "bubbles":[
      {"id":"b1","kind":"answer","text":"Yes, for about 4 months. Your savings cover your bills and mortgage until April."},
      {"id":"b2","kind":"caveat","text":"This assumes your bills stay the same and you spend nothing extra."}],
     "highlights":[{"bubble_id":"b1","start":15,"length":8,"fact_id":"f_cover","source_id":"s_you"}],
     "facts":[{"id":"f_cover","value":4.0,"unit":"months","label":"Months of cover","source_id":"s_you"}],
     "sources":[
      {"id":"s_you","group":"your_data","label":"Your accounts","ref":{"source":"bank","series_id":"your-accounts","status":"live"},"updated_at":"2026-10-17T12:00:00Z"},
      {"id":"s_boe","group":"live_sources","label":"Bank of England · live","ref":{"source":"boe","series_id":"IUMBEDR","status":"live"},"updated_at":"2026-10-17T12:00:00Z"},
      {"id":"s_gk","group":"general_knowledge","label":"How emergency funds work"}],
     "mode":"checked",
     "suggestions":["Add a holiday in June","Summary"],
     "confidence":0.8,
     "tool_calls":[{"name":"cash_flow_projection","ok":true,"duration_ms":120}],
     "verified":true,"summary_available":false,"links":["test_it","why"],"disclaimer":"Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions."}
    """

    static let moneyJSON = """
    {"thread_id":"th_1","message_id":"msg_4","reply_to":"msg_3","reaction":"eyes",
     "bubbles":[{"id":"b1","kind":"answer","text":"A 5-year fix costs £1,050 a month. That is £16 less than a 2-year fix."}],
     "highlights":[
      {"bubble_id":"b1","start":19,"length":6,"fact_id":"f_pay","source_id":"s_boe"},
      {"bubble_id":"b1","start":43,"length":3,"fact_id":"f_gap","source_id":"s_boe"}],
     "facts":[
      {"id":"f_pay","value":1050,"unit":"gbp_per_month","label":"5-year fix payment","source_id":"s_boe"},
      {"id":"f_gap","value":16,"unit":"gbp_per_month","label":"Monthly saving","source_id":"s_boe"}],
     "sources":[{"id":"s_boe","group":"live_sources","label":"Bank of England · live","ref":{"source":"boe","series_id":"IUMBV42","status":"live"},"updated_at":"2026-10-17T09:05:00Z"}],
     "mode":"checked","confidence":0.6,"verified":true,"links":["next_move"],"disclaimer":"Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions."}
    """

    static let shrugJSON = """
    {"thread_id":"th_2","message_id":"msg_6","reply_to":"msg_5","reaction":"shrug",
     "bubbles":[{"id":"b1","kind":"answer","text":"I can't pick shares. I can help with your next money move."}],
     "mode":"general","confidence":0.3,"verified":true,"links":["next_move"],"sources":[],"disclaimer":"Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions."}
    """

    static let generalJSON = """
    {"thread_id":"th_3","message_id":"msg_8","reply_to":"msg_7","reaction":"brain","mode":"general",
     "bubbles":[{"id":"b1","kind":"general_knowledge","text":"A bursary is money from your university that you do not pay back. Ask the student support team which ones you can get."}],
     "sources":[{"id":"s_web","group":"general_knowledge","label":"UCAS · student finance guide","url":"https://www.ucas.com"}],
     "suggestions":["How do I apply?"],
     "confidence":0.7,"verified":true,"disclaimer":"Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions."}
    """

    static func decode<T: Decodable>(_ type: T.Type, _ json: String) -> T {
        do {
            return try JSONDecoder().decode(T.self, from: Data(json.utf8))
        } catch {
            fatalError("Penny fixture does not match the contract: \(error)")
        }
    }

    static var answerResponse: PennyAPI.Response { decode(PennyAPI.Response.self, answerJSON) }
    static var moneyResponse: PennyAPI.Response { decode(PennyAPI.Response.self, moneyJSON) }
    static var shrugResponse: PennyAPI.Response { decode(PennyAPI.Response.self, shrugJSON) }
    static var generalResponse: PennyAPI.Response { decode(PennyAPI.Response.self, generalJSON) }

    static func event(_ json: String) -> PennyAPI.StreamEvent { decode(PennyAPI.StreamEvent.self, json) }

    /// The streamed form of `answerResponse`: reaction, 2 real tool steps, verifying, 3 bubbles, done.
    static var answerEvents: [PennyAPI.StreamEvent] {
        let bubbles = answerResponse.bubbles
        let highlights = answerResponse.highlights ?? []
        var events = [
            event(#"{"type":"reaction","seq":0,"elapsed_ms":300,"reaction":"brain"}"#),
            event(#"{"type":"tool_step","seq":1,"elapsed_ms":500,"step":{"tool":"finance_summary","label":"Reading your accounts…"}}"#),
            event(#"{"type":"tool_step","seq":2,"elapsed_ms":900,"step":{"tool":"cash_flow_projection","label":"Projecting your cash…"}}"#),
            event(#"{"type":"verifying","seq":3,"elapsed_ms":2100,"step":null}"#),
        ]
        for (index, bubble) in bubbles.enumerated() {
            let payload = Components.Schemas.BubbleEvent(bubble: bubble, highlights: highlights.filter { $0.bubbleId == bubble.id })
            var item = event(#"{"type":"bubble","seq":0,"elapsed_ms":0}"#)
            item.seq = 4 + index
            item.elapsedMs = 2_400 + index * 400
            item.bubble = payload
            events.append(item)
        }
        var done = event(#"{"type":"done","seq":0,"elapsed_ms":3600}"#)
        done.seq = 4 + bubbles.count
        done.response = answerResponse
        events.append(done)
        return events
    }

    /// A service that plays `events` (or throws `streamError` after them) and answers `ask` with `fallback`.
    nonisolated static func scripted(
        events: [PennyAPI.StreamEvent],
        streamError: (any Error)? = nil,
        fallback: PennyAPI.Response? = nil,
        threads: PennyAPI.ThreadsResponse = .init(threads: []),
        gap: Duration = .zero,
        sleep: @escaping @Sendable (Duration) async throws -> Void = { _ in },
        now: Date = Date()
    ) -> PennyService {
        PennyService(
            ask: { _ in
                guard let fallback else { throw URLError(.notConnectedToInternet) }
                return fallback
            },
            stream: { _ in
                AsyncThrowingStream { continuation in
                    let task = Task {
                        for item in events {
                            if gap > .zero { try? await Task.sleep(for: gap) }
                            continuation.yield(item)
                        }
                        continuation.finish(throwing: streamError)
                    }
                    continuation.onTermination = { _ in task.cancel() }
                }
            },
            loadThreads: { onUpdate in await onUpdate(threads) },
            getThread: { _ in throw URLError(.fileDoesNotExist) },
            sleep: sleep,
            now: { now }
        )
    }

    // MARK: View states

    private static func base(rows: [PennyViewState.Row], working: Bool = false, mood: PennyMood = .smiling) -> PennyViewState {
        var state = PennyViewState(
            title: "Ask Penny",
            openThreadQuestionID: nil,
            rows: rows,
            chips: rows.isEmpty ? PennyViewModel.chips : [],
            pastThreads: [],
            isWorking: working,
            canSend: !working,
            pennyMood: mood,
            openHighlightID: nil,
            expandedSourceGroups: [],
            isPresentation: false,
            inputPlaceholder: "Ask Penny anything"
        )
        state.pennyFaceRowID = rows.last { if case .question = $0 { false } else { true } }?.id
        if !working, case let .answer(group)? = rows.last, !group.suggestions.isEmpty {
            state.suggestionsGroupID = group.id
        }
        return state
    }

    private static func question(_ id: String, _ text: String, _ reaction: PennyReaction?, replies: Int = 0) -> PennyViewState.Row {
        .question(.init(id: id, text: text, reaction: reaction, replyCount: replies, isReply: false))
    }

    static var empty: PennyViewState {
        var state = base(rows: [])
        state.pastThreads = [.init(id: "th_1", title: "What if I lose my job?", detail: "2 messages · 17 Oct")]
        return state
    }

    static var thinking: PennyViewState {
        base(rows: [question("local-1", "What if I lose my job?", .brain), .working(id: "local-1", step: nil)], working: true, mood: .thinking)
    }

    static var streamingStep: PennyViewState {
        let partial = PennyMapping.answerGroup(answerResponse, presentation: false, now: now, isComplete: false)
        var group = partial
        group.bubbles = Array(partial.bubbles.prefix(1))
        return base(
            rows: [
                question("local-1", "What if I lose my job?", .brain),
                .answer(group),
                .working(id: "local-1", step: "Projecting your cash…"),
            ],
            working: true, mood: .thinking
        )
    }

    static var answer: PennyViewState {
        var state = base(
            rows: [question("msg_1", "What if I lose my job?", .brain, replies: 1),
                   .answer(PennyMapping.answerGroup(answerResponse, presentation: false, now: now))],
            mood: .happy
        )
        state.openHighlightID = "msg_2.b1.0"
        return state
    }

    static var sourcesExpanded: PennyViewState {
        var state = answer
        state.openHighlightID = nil
        state.expandedSourceGroups = ["msg_2"]
        return state
    }

    static var thread: PennyViewState {
        var state = base(
            rows: [
                .question(.init(id: "msg_1", text: "What if I lose my job?", reaction: .brain, replyCount: 0, isReply: false)),
                .answer(PennyMapping.answerGroup(answerResponse, presentation: false, now: now)),
                .question(.init(id: "msg_3", text: "Should I fix for 5 years?", reaction: .eyes, replyCount: 0, isReply: true)),
                .answer(PennyMapping.answerGroup(moneyResponse, presentation: false, now: now)),
            ],
            mood: .thinking
        )
        state.title = "Thread"
        state.openThreadQuestionID = "msg_1"
        state.chips = []
        state.inputPlaceholder = "Reply in this thread"
        return state
    }

    static var shrug: PennyViewState {
        base(
            rows: [question("msg_5", "Which shares should I buy?", .shrug, replies: 1),
                   .answer(PennyMapping.answerGroup(shrugResponse, presentation: false, now: now))],
            mood: .neutral
        )
    }

    static var general: PennyViewState {
        base(
            rows: [question("msg_7", "What is a bursary?", .brain, replies: 1),
                   .answer(PennyMapping.answerGroup(generalResponse, presentation: false, now: now))],
            mood: .thinking
        )
    }

    static var unavailable: PennyViewState {
        base(rows: [question("local-1", "Can I afford a holiday in June?", .eyes),
                    .failed(id: "local-1", error: PennyViewModel.unavailableError)])
    }

    static var all: [(id: String, title: String, state: PennyViewState)] {
        [
            ("penny.empty", "Empty, earlier chats", empty),
            ("penny.thinking", "Thinking (reaction set)", thinking),
            ("penny.streaming", "Streaming, tool step", streamingStep),
            ("penny.answer", "Answer, caveat, question, number card", answer),
            ("penny.sources", "Sources expanded", sourcesExpanded),
            ("penny.thread", "Thread view", thread),
            ("penny.shrug", "Out of scope (shrug)", shrug),
            ("penny.general", "General answer", general),
            ("penny.unavailable", "Penny unavailable", unavailable),
        ]
    }
}
