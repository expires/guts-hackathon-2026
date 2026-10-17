import Foundation
import Testing
@testable import Lifeline

/// Ask Penny (ADR 0031, perceived-speed amendment). W7.
@MainActor
@Suite("Ask Penny ViewModel")
struct PennyViewModelTests {
    /// Records each typing pause and how many Penny bubbles were on screen when it started.
    final class PauseLog: @unchecked Sendable {
        var pauses: [Duration] = []
        var visibleAtPause: [Int] = []
        weak var model: PennyViewModel?
    }

    static func bubbleCount(_ state: PennyViewState) -> Int {
        state.rows.reduce(0) { count, row in
            if case let .answer(group) = row { return count + group.bubbles.count }
            return count
        }
    }

    static func groups(_ state: PennyViewState) -> [PennyViewState.AnswerGroup] {
        state.rows.compactMap { if case let .answer(group) = $0 { group } else { nil } }
    }

    func makeModel(
        events: [PennyAPI.StreamEvent],
        streamError: (any Error)? = nil,
        fallback: PennyAPI.Response? = nil,
        log: PauseLog = PauseLog()
    ) -> PennyViewModel {
        let service = PennyFixtures.scripted(
            events: events, streamError: streamError, fallback: fallback,
            sleep: { [log] duration in
                let visible = await MainActor.run { log.model.map { PennyViewModelTests.bubbleCount($0.state) } ?? -1 }
                log.pauses.append(duration)
                log.visibleAtPause.append(visible)
            },
            now: PennyFixtures.now
        )
        let model = PennyViewModel(service: service, context: PennyContext(screen: .money))
        log.model = model
        return model
    }

    // MARK: Stream ordering

    @Test func streamShowsReactionStepsThenBubblesInOrder() async throws {
        let log = PauseLog()
        let model = makeModel(events: PennyFixtures.answerEvents, log: log)
        model.send("What if I lose my job?")
        #expect(model.isWorking)
        await model.waitForTurn()

        let state = model.state
        #expect(!state.isWorking)
        guard case let .question(question) = state.rows.first else { Issue.record("no question row"); return }
        // The server's message id replaces the local id.
        #expect(question.id == "msg_1")
        #expect(question.reaction == .brain)
        #expect(question.replyCount == 1)
        let group = try #require(Self.groups(state).first)
        #expect(group.bubbles.map(\.id) == ["b1", "b2"])
        #expect(group.bubbles.map(\.kind) == [.answer, .caveat])
        #expect(group.modeLabel == "Checked with your data")
        #expect(group.suggestions == ["Add a holiday in June", "Summary"])
        #expect(state.suggestionsGroupID == group.id)
        // Penny's face shows once, on the newest Penny row.
        #expect(state.pennyFaceRowID == "a.msg_2")
        #expect(group.isComplete)
        #expect(group.links == [.testIt, .why])
        #expect(state.pennyMood == .happy)
        // One typing pause per bubble, each before its bubble appears.
        #expect(log.pauses.count == 2)
        #expect(log.visibleAtPause == [0, 1])
        #expect(model.threadID == "th_1")
    }

    static func workingSteps(_ state: PennyViewState) -> [String?] {
        state.rows.compactMap { if case let .working(_, step) = $0 { step } else { nil } }
    }

    /// Polls the main actor until `condition` holds (at most about 2 s).
    func waitUntil(_ condition: () -> Bool) async {
        for _ in 0..<400 where !condition() {
            try? await Task.sleep(for: .milliseconds(5))
        }
    }

    @Test func toolStepUpdatesInPlaceAndIgnoresRepeatedSeq() async throws {
        let (stream, continuation) = AsyncThrowingStream<PennyAPI.StreamEvent, any Error>.makeStream()
        var service = PennyFixtures.scripted(events: [], fallback: PennyFixtures.answerResponse, now: PennyFixtures.now)
        service.stream = { _ in stream }
        let model = PennyViewModel(service: service)
        model.send("What if I lose my job?")
        let events = PennyFixtures.answerEvents
        continuation.yield(events[0])
        await waitUntil { model.exchanges.first?.reaction == .brain }
        // The reaction arrives before any step or bubble.
        #expect(model.exchanges.first?.reaction == .brain)
        #expect(Self.bubbleCount(model.state) == 0)
        continuation.yield(events[1])
        continuation.yield(events[2])
        continuation.yield(events[1]) // repeated seq: dropped
        await waitUntil { Self.workingSteps(model.state) == ["Projecting your cash…"] }
        #expect(Self.workingSteps(model.state) == ["Projecting your cash…"])
        continuation.yield(events[3])
        await waitUntil { Self.workingSteps(model.state) == [PennyViewModel.verifyingLabel] }
        // One grey line, updated in place.
        #expect(Self.workingSteps(model.state) == [PennyViewModel.verifyingLabel])
        for event in events.dropFirst(4) { continuation.yield(event) }
        continuation.finish()
        await model.waitForTurn()
        #expect(Self.workingSteps(model.state).isEmpty)
        #expect(Self.bubbleCount(model.state) == 2)
    }

    @Test func typingPauseScalesWithLength() {
        #expect(PennyViewModel.typingPause(for: "Yes.") >= .milliseconds(400))
        #expect(PennyViewModel.typingPause(for: "Yes.") < .milliseconds(420))
        #expect(PennyViewModel.typingPause(for: String(repeating: "a", count: 120)) == .milliseconds(550))
        #expect(PennyViewModel.typingPause(for: String(repeating: "a", count: 600)) == .milliseconds(700))
    }

    // MARK: Fallback

    @Test func streamErrorFallsBackToAskPenny() async throws {
        let firstBubble = Array(PennyFixtures.answerEvents.prefix(5))
        let model = makeModel(events: firstBubble, streamError: URLError(.networkConnectionLost), fallback: PennyFixtures.answerResponse)
        model.send("What if I lose my job?")
        await model.waitForTurn()
        let groups = Self.groups(model.state)
        #expect(groups.count == 1)
        #expect(groups[0].bubbles.map(\.id) == ["b1", "b2"])
        #expect(groups[0].isComplete)
    }

    @Test func streamEndingWithoutDoneFallsBack() async throws {
        let model = makeModel(events: Array(PennyFixtures.answerEvents.prefix(2)), fallback: PennyFixtures.moneyResponse)
        model.send("Should I fix for 5 years?")
        await model.waitForTurn()
        let group = try #require(Self.groups(model.state).first)
        #expect(group.id == "msg_4")
    }

    @Test func failedFallbackRemovesStreamedBubblesAndOffersRetry() async throws {
        let firstBubble = Array(PennyFixtures.answerEvents.prefix(5))
        let model = makeModel(events: firstBubble, streamError: URLError(.networkConnectionLost))
        model.send("What if I lose my job?")
        await model.waitForTurn()
        #expect(Self.bubbleCount(model.state) == 0)
        let failed = model.state.rows.contains { if case .failed = $0 { true } else { false } }
        #expect(failed)
        #expect(model.state.canSend)
    }

    // MARK: Verified bubbles only

    @Test func doneResponseReplacesStreamedBubbles() async throws {
        // The stream sent b1 and b2, then an error and a template summary with only "t1" (verified false).
        var template = PennyFixtures.moneyResponse
        template.messageId = "msg_2"
        template.replyTo = "msg_1"
        template.verified = false
        template.bubbles = [.init(id: "t1", kind: .answer, text: "Here is a short summary from the tools.")]
        template.highlights = []
        var events = Array(PennyFixtures.answerEvents.prefix(6))
        var error = PennyFixtures.event(#"{"type":"error","seq":6,"elapsed_ms":3000,"error_code":"verifier_failed"}"#)
        error.seq = 6
        var done = PennyFixtures.event(#"{"type":"done","seq":7,"elapsed_ms":3100}"#)
        done.response = template
        events += [error, done]

        let model = makeModel(events: events)
        model.send("What if I lose my job?")
        await model.waitForTurn()
        let groups = Self.groups(model.state)
        #expect(groups.count == 1)
        #expect(groups[0].bubbles.map(\.id) == ["t1"])
        #expect(!groups[0].isVerified)
    }

    @Test func emptyBubbleEventIsNotShown() async throws {
        var events = Array(PennyFixtures.answerEvents.prefix(4))
        var empty = PennyFixtures.event(#"{"type":"bubble","seq":4,"elapsed_ms":2000}"#)
        empty.bubble = .init(bubble: .init(id: "bx", kind: .answer, text: ""))
        events.append(empty)
        let model = makeModel(events: events, streamError: URLError(.networkConnectionLost))
        model.send("Hi")
        await model.waitForTurn()
        #expect(Self.bubbleCount(model.state) == 0)
    }

    // MARK: Highlights

    @Test func highlightMapsToFactAndSource() throws {
        let group = PennyMapping.answerGroup(PennyFixtures.moneyResponse, presentation: false, now: PennyFixtures.now)
        let first = try #require(group.bubbles.first)
        #expect(first.segments.compactMap { $0.highlightID == nil ? nil : $0.text } == ["£1,050", "£16"])
        let detail = try #require(group.highlights["msg_4.b1.0"])
        #expect(detail.label == "5-year fix payment")
        #expect(detail.valueText == "£1,050 a month")
        // Human source name from the server, never a series code (fix 5).
        #expect(detail.sourceLabel == "Bank of England · live")
        #expect(detail.updatedText == "Updated 3 h ago")
        #expect(detail.status == .live)
        #expect(group.sourcesTitle == "See sources")
        #expect(group.disclaimer == PennyMapping.disclaimer)
        let all = PennyMapping.answerGroup(PennyFixtures.answerResponse, presentation: false, now: PennyFixtures.now)
        #expect(all.sourceGroups.map(\.title) == ["Your data", "Live sources", "General knowledge"])
        #expect(!all.sourceGroups.flatMap(\.rows).map(\.label).contains { $0.contains("IUMB") })
    }

    @Test func onlyMoneyAndRatesAreHighlighted() throws {
        // "4 months" (unit months) is a number but not money or a rate: plain text (fix 6).
        let group = PennyMapping.answerGroup(PennyFixtures.answerResponse, presentation: false, now: PennyFixtures.now)
        let first = try #require(group.bubbles.first)
        #expect(first.segments.allSatisfy { $0.highlightID == nil })
        #expect(group.highlights.isEmpty)
        #expect(PennyMapping.isHighlightable("percent"))
        #expect(PennyMapping.isHighlightable("gbp_per_month"))
        #expect(!PennyMapping.isHighlightable("date_year"))
        #expect(!PennyMapping.isHighlightable("months"))
    }

    @Test func generalAnswerIsLabelled() {
        let group = PennyMapping.answerGroup(PennyFixtures.generalResponse, presentation: false, now: PennyFixtures.now)
        #expect(group.modeLabel == "General answer")
        #expect(!group.isChecked)
        #expect(group.suggestions == ["How do I apply?"])
    }

    @Test func officialSourcesOnlyHaveTheirOwnLabel() {
        // The money answer used only Bank of England data: no "your_data" source.
        let group = PennyMapping.answerGroup(PennyFixtures.moneyResponse, presentation: false, now: PennyFixtures.now)
        #expect(group.modeLabel == "Checked against official sources")
        #expect(group.isChecked)
    }

    @Test func loneYesSuggestionIsDropped() {
        var response = PennyFixtures.answerResponse
        response.suggestions = ["Yes"]
        #expect(PennyMapping.answerGroup(response, presentation: false, now: PennyFixtures.now).suggestions.isEmpty)
    }

    @Test func badHighlightsAreDropped() {
        let text = "£1,050 a month 🙂 then £16"
        let highlights: [PennyAPI.Highlight] = [
            .init(bubbleId: "b1", start: 0, length: 6, factId: "a"),
            .init(bubbleId: "b1", start: 3, length: 4, factId: "overlap"),
            .init(bubbleId: "b1", start: 22, length: 3, factId: "b"),
            .init(bubbleId: "b1", start: 40, length: 2, factId: "outside"),
            .init(bubbleId: "b2", start: 0, length: 2, factId: "other bubble"),
        ]
        let spans = PennyMapping.spans(for: "b1", text: text, highlights: highlights)
        #expect(spans.map(\.factID) == ["a", "b"])
        let segments = PennyMapping.segments(text: text, spans: spans, idPrefix: "g.b1")
        #expect(segments.compactMap { $0.highlightID == nil ? nil : $0.text } == ["£1,050", "£16"])
        #expect(segments.map(\.text).joined() == text)
    }

    @Test func presentationModeRoundsMoneyOnly() throws {
        let group = PennyMapping.answerGroup(PennyFixtures.moneyResponse, presentation: true, now: PennyFixtures.now)
        let bubble = try #require(group.bubbles.first)
        // £1,050 to the nearest £100, £16 to the nearest £10 (DesignSystem LLAmountFormat).
        #expect(bubble.text == "A 5-year fix costs £1,100 a month. That is £20 less than a 2-year fix.")
        #expect(group.highlights["msg_4.b1.0"]?.valueText == "£1,100 a month")
        let months = PennyMapping.answerGroup(PennyFixtures.answerResponse, presentation: true, now: PennyFixtures.now)
        #expect(months.bubbles[0].text.contains("4 months"))
        #expect(PennyMapping.roundedAmountText("-£1,234") == "-£1,200")
        #expect(PennyMapping.roundedAmountText("4 months") == nil)
    }

    @Test func tappingAHighlightTogglesItsCard() async {
        let model = makeModel(events: PennyFixtures.answerEvents)
        model.send("What if I lose my job?")
        await model.waitForTurn()
        model.toggleHighlight("msg_2.b1.0")
        #expect(model.state.openHighlightID == "msg_2.b1.0")
        model.toggleHighlight("msg_2.b1.0")
        #expect(model.state.openHighlightID == nil)
    }

    // MARK: Threads

    @Test func replyInsideAThreadStaysInTheThread() async throws {
        let model = makeModel(events: PennyFixtures.answerEvents)
        model.send("What if I lose my job?")
        await model.waitForTurn()
        model.openThread("msg_1")
        model.send("Add a holiday in June")
        await model.waitForTurn()
        // The reply sits in the thread, not in the main chat.
        #expect(model.exchanges.last?.rootID == "msg_1")
        #expect(model.replyCount(rootID: "msg_1") == 2)
        model.closeThread()
        let mainQuestions = model.state.rows.filter { if case .question = $0 { true } else { false } }
        #expect(mainQuestions.count == 1)
    }

    @Test func loadsAStoredThread() {
        let model = makeModel(events: [])
        let thread = PennyFixtures.decode(PennyAPI.Thread.self, """
        {"id":"th_1","title":"What if I lose my job?","messages":[
          {"id":"msg_1","role":"user","created_at":"2026-10-17T12:00:00Z","text":"What if I lose my job?","replies":1},
          {"id":"msg_2","role":"penny","created_at":"2026-10-17T12:00:00Z","reply_to":"msg_1","response":\(PennyFixtures.answerJSON)}
        ]}
        """)
        model.apply(thread: thread)
        let state = model.state
        #expect(state.rows.count == 2)
        guard case let .question(question) = state.rows[0] else { Issue.record("no question"); return }
        #expect(question.replyCount == 1)
        #expect(question.reaction == .brain)
    }

    @Test func starterChipsOnlyOnAnEmptyChat() async {
        let model = makeModel(events: PennyFixtures.answerEvents)
        #expect(model.state.chips == PennyViewModel.chips)
        model.send("Can I afford a holiday in June?")
        #expect(model.state.chips.isEmpty)
        #expect(!model.state.canSend)
        // The face sits on the typing row while Penny works.
        #expect(model.state.pennyFaceRowID == "w.local-1")
        await model.waitForTurn()
        // After the first message the starter chips never come back (fix 8).
        #expect(model.state.chips.isEmpty)
        #expect(model.state.suggestionsGroupID == "msg_2")
    }

    // MARK: Penny tab (step 2 glue)

    @Test func tabAskSendsTheContextQuestionIntoOneChat() async {
        let tab = PennyTabModel(service: PennyFixtures.scripted(events: PennyFixtures.answerEvents, now: PennyFixtures.now))
        #expect(!tab.chat.state.showsClose)
        #expect(tab.chat.state.title == "Penny")
        tab.ask(PennyContext(screen: .nextMove, nextMoveID: "mv_1", question: "Why this move?"))
        // A second ask while Penny works waits for the turn, then goes into the same chat.
        tab.ask(PennyContext(screen: .money, question: "What is my weekly budget?"))
        await tab.chat.waitForTurn()
        await tab.chat.waitForTurn()
        #expect(tab.chat.exchanges.map(\.text) == ["Why this move?", "What is my weekly budget?"])
        #expect(tab.chat.context.screen == .money)
    }

    @Test func starterChipsNeverReturnAfterANewContext() async {
        let tab = PennyTabModel(service: PennyFixtures.scripted(events: PennyFixtures.answerEvents, now: PennyFixtures.now))
        #expect(tab.chat.state.chips == PennyViewModel.chips)
        tab.ask(PennyContext(screen: .money, question: "What is my weekly budget?"))
        await tab.chat.waitForTurn()
        #expect(tab.chat.state.chips.isEmpty)
        // A new context from "Ask Penny" (no question) does not bring the starter chips back.
        tab.ask(PennyContext(screen: .nextMove, nextMoveID: "mv_1"))
        #expect(tab.chat.state.chips.isEmpty)
        // Follow-up chips come only from the server's `suggestions`, under the newest answer.
        #expect(tab.chat.state.suggestionsGroupID == "msg_2")
    }

    @Test func toolStepShowsTheServerLabel() async {
        let (stream, continuation) = AsyncThrowingStream<PennyAPI.StreamEvent, any Error>.makeStream()
        var service = PennyFixtures.scripted(events: [], fallback: PennyFixtures.answerResponse, now: PennyFixtures.now)
        service.stream = { _ in stream }
        let model = PennyViewModel(service: service)
        model.send("Can I afford a holiday that costs 1 million yuan?")
        continuation.yield(PennyFixtures.event(#"{"type":"tool_step","seq":1,"elapsed_ms":400,"step":{"tool":"fx_convert","label":"Checking exchange rates…"}}"#))
        await waitUntil { Self.workingSteps(model.state) == ["Checking exchange rates…"] }
        #expect(Self.workingSteps(model.state) == ["Checking exchange rates…"])
        continuation.finish()
        await model.waitForTurn()
    }

    @Test func tabAskWithoutQuestionOnlySetsContext() {
        let tab = PennyTabModel(service: PennyFixtures.scripted(events: []))
        tab.ask(PennyContext(screen: .lifeEvent, lifeID: "lf_1", eventID: "ev_1"))
        #expect(tab.chat.exchanges.isEmpty)
        #expect(tab.chat.context.eventID == "ev_1")
    }

    // MARK: Keepalive and failure (fix 9)

    @Test func keepaliveKeepsTheStreamOpen() async throws {
        let (stream, continuation) = AsyncThrowingStream<PennyAPI.StreamEvent, any Error>.makeStream()
        var service = PennyFixtures.scripted(events: [], fallback: PennyFixtures.moneyResponse, now: PennyFixtures.now)
        service.stream = { _ in stream }
        let model = PennyViewModel(service: service, streamIdleTimeout: .milliseconds(300))
        model.send("What if I lose my job?")
        let events = PennyFixtures.answerEvents
        continuation.yield(events[0])
        // 6 keepalives 100 ms apart: 600 ms in all, longer than the 300 ms idle timeout.
        for index in 0..<6 {
            try await Task.sleep(for: .milliseconds(100))
            var keepalive = PennyFixtures.event(#"{"type":"keepalive","seq":0,"elapsed_ms":0}"#)
            keepalive.seq = 100 + index
            continuation.yield(keepalive)
        }
        var rest = Array(events.dropFirst())
        for index in rest.indices { rest[index].seq += 200 }
        for event in rest { continuation.yield(event) }
        continuation.finish()
        await model.waitForTurn()
        // The streamed answer (msg_2), not the fallback (msg_4).
        #expect(Self.groups(model.state).map(\.id) == ["msg_2"])
    }

    @Test func silentStreamFallsBack() async throws {
        let (stream, continuation) = AsyncThrowingStream<PennyAPI.StreamEvent, any Error>.makeStream()
        var service = PennyFixtures.scripted(events: [], fallback: PennyFixtures.moneyResponse, now: PennyFixtures.now)
        service.stream = { _ in stream }
        let model = PennyViewModel(service: service, streamIdleTimeout: .milliseconds(200))
        model.send("What if I lose my job?")
        continuation.yield(PennyFixtures.answerEvents[0])
        await model.waitForTurn()
        #expect(Self.groups(model.state).map(\.id) == ["msg_4"])
        continuation.finish()
    }

    @Test func failureShowsPennyIsUnavailable() async throws {
        let model = makeModel(events: [], streamError: URLError(.timedOut))
        model.send("What if I lose my job?")
        await model.waitForTurn()
        let failed = model.state.rows.compactMap { if case let .failed(_, error) = $0 { error } else { nil } }
        #expect(failed.first?.title == "Penny is unavailable right now. Try again.")
        #expect(failed.first?.canRetry == true)
    }

    @Test func contextIsSentWithTheRequest() async {
        final class Box: @unchecked Sendable { var request: PennyAPI.Request? }
        let box = Box()
        var service = PennyFixtures.scripted(events: [], fallback: PennyFixtures.answerResponse)
        let inner = service.stream
        service.stream = { request in
            box.request = request
            return inner(request)
        }
        let model = PennyViewModel(service: service, context: PennyContext(screen: .lifeEvent, lifeID: "lf_1", eventID: "ev_1", question: "What should I pick?"))
        await model.start()
        await model.waitForTurn()
        #expect(box.request?.message == "What should I pick?")
        #expect(box.request?.context?.screen?.rawValue == "life_event")
        #expect(box.request?.context?.lifeId == "lf_1")
        #expect(box.request?.context?.eventId == "ev_1")
    }
}

/// You tab additions (W7): Version row and "Connect your money".
@Suite("You tab build info")
struct YouBuildInfoTests {
    @Test func readsCheckpointBuildTimeAndFeatures() {
        let info = YouBuildInfo.make(
            info: ["CFBundleShortVersionString": "1.2", "CFBundleVersion": "12", "LifelineCheckpoint": "3",
                   "LifelineBuildTime": "2026-10-17T17:04:00Z", "LifelineFeatures": "Penny, Accounts ,"],
            bundleID: "com.lifeline.app.dev", timeZone: TimeZone(identifier: "UTC")!
        )
        #expect(info.appName == "\(Brand.productName) Dev")
        #expect(info.title == "\(Brand.productName) Dev 1.2 (build 12)")
        #expect(info.detailLines == ["Checkpoint 3", "Built 17 Oct 2026, 17:04", "Features: Penny, Accounts"])
    }

    @Test func missingKeysAreLeftOut() {
        let info = YouBuildInfo.make(
            info: ["CFBundleShortVersionString": "1.0", "CFBundleVersion": "7", "LifelineCheckpoint": "",
                   "LifelineBuildTime": "$(LIFELINE_BUILD_TIME)"],
            bundleID: "com.lifeline.app"
        )
        #expect(info.appName == Brand.productName)
        // A Demo build without checkpoint keys: never "dev build".
        #expect(info.title == "\(Brand.productName) 1.0 (build 7)")
        #expect(info.detailLines.isEmpty)
    }

    @Test @MainActor func cutSourcesAreHidden() {
        let rows = [("boe", "Bank of England"), ("truelayer", "TrueLayer open banking"), ("trading212", "Trading 212"),
                    ("adzuna", "Adzuna jobs"), ("dvla", "DVLA"), ("monzo", "Monzo")]
        let json = "[" + rows.map { id, name in
            #"{"id":"\#(id)","name":"\#(name)","status":"live","ttl_seconds":3600,"coverage":"UK","attribution":"x","licence":"OGL"}"#
        }.joined(separator: ",") + "]"
        guard let sources = try? JSONDecoder().decode([SourceStatus].self, from: Data(json.utf8)) else {
            Issue.record("SourceStatus shape changed"); return
        }
        #expect(sources.filter { !YouViewModel.isCutSource($0) }.map(\.id) == ["boe"])
    }

    @Test @MainActor func evaluationRowNeedsCases() {
        let none = YouViewModel.makeState(profile: nil, phase: .ready, clientKind: .mock, isDebugBuild: false, evaluationCount: 0)
        #expect(!none.showsEvaluation)
        let some = YouViewModel.makeState(profile: nil, phase: .ready, clientKind: .mock, isDebugBuild: false, evaluationCount: 120)
        #expect(some.showsEvaluation)
    }

    @Test @MainActor func connectMoneyText() {
        #expect(YouViewModel.connectMoneyText(inputs: ["statement", "bank"], failed: false) == "Statement imported")
        #expect(YouViewModel.connectMoneyText(inputs: ["bank"], failed: false) == "Money added")
        #expect(YouViewModel.connectMoneyText(inputs: ["sample"], failed: false) == "Sample statement")
        #expect(YouViewModel.connectMoneyText(inputs: ["statement"], failed: false) == "Statement imported")
        #expect(YouViewModel.connectMoneyText(inputs: [], failed: false) == "Not added yet")
        #expect(YouViewModel.profileLine(age: 20, occupation: "student", housing: "rent") == "Age 20 · Student · Renting")
        #expect(YouViewModel.profileLine(age: 34, occupation: "nurse", housing: "parents") == "Age 34 · Working · Lives with family")
        #expect(YouViewModel.profileLine(age: 19, isStudent: true, occupation: "barista", housing: "parents") == "Age 19 · Student · Lives with family")
        #expect(YouViewModel.profileLine(age: 25, isStudent: false, occupation: "student nurse", housing: "own") == "Age 25 · Working · Owns a home")
        #expect(YouViewModel.connectMoneyText(inputs: nil, failed: true) == "Couldn't load. Pull to refresh.")
        #expect(YouViewModel.connectMoneyText(inputs: nil, failed: false) == nil)
        #expect(YouViewModel.calmError(.server(status: 429, code: "rate_limited", message: "Too many requests", source: "api")).message == "Pull to refresh.")
    }
}

/// "How Penny uses AI" (ADR 0043). W7.
@Suite("AI disclosure")
struct AIDisclosureTests {
    @Test func bundledFileHasTheFourSections() {
        let state = AIDisclosureViewState.load()
        #expect(state != AIDisclosureViewState.fallback)
        #expect(state.sections.map(\.heading) == [
            "Where AI is used", "What stays deterministic", "How output is checked", "What happens when AI fails",
        ])
        #expect(state.sections.allSatisfy { !$0.points.isEmpty })
    }
}
