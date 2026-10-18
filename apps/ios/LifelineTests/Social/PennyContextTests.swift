import Foundation
import Testing
@testable import Lifeline

/// "Ask Penny" carries its context (W7): context mapping, thread titles, new chats, starter chips.
@MainActor
@Suite("Ask Penny context")
struct PennyContextTests {
    /// Records every chat request the service receives.
    final class RequestLog: @unchecked Sendable {
        var requests: [PennyAPI.Request] = []
    }

    func capturingService(_ log: RequestLog) -> PennyService {
        let scripted = PennyFixtures.scripted(events: PennyFixtures.answerEvents, now: PennyFixtures.now)
        var service = scripted
        service.stream = { [log] request in
            log.requests.append(request)
            return scripted.stream(request)
        }
        return service
    }

    // MARK: Entry point contexts

    @Test func soloLifeEventAsksWhichOptionAndTitlesFromTheEvent() {
        let context = PennyContext.lifeEvent(lifeID: "lf_1", eventID: "ev_1", eventTitle: "Safety fund", age: 19)
        #expect(context.screen == .lifeEvent)
        #expect(context.question == "Which option should I pick?")
        #expect(context.threadTitle == "Safety fund, age 19")
        #expect(!context.isMultiplayer)

        let wire = PennyMapping.chatContext(context, isNewThread: true)
        #expect(wire.screen?.rawValue == "life_event")
        #expect(wire.lifeId == "lf_1")
        #expect(wire.eventId == "ev_1")
        #expect(wire.title == "Safety fund, age 19")
        #expect(wire.multiplayer == nil)
        #expect(wire.roomCode == nil)
    }

    @Test func roomLifeEventIsMultiplayerAndDoesNotAskPennyToPick() {
        let context = PennyContext.lifeEvent(lifeID: "lf_1", eventID: "ev_1", eventTitle: "Rent rise", age: 21, roomCode: "LEEDS4")
        #expect(context.isMultiplayer)
        #expect(context.question == "What are the trade-offs here?")
        let wire = PennyMapping.chatContext(context, isNewThread: true)
        #expect(wire.multiplayer == true)
        #expect(wire.roomCode == "LEEDS4")
        #expect(wire.title == "Rent rise, age 21")
    }

    @Test func sameDecisionRoundSendsRoomAndRound() {
        let context = PennyContext.roomRound(roomCode: "LEEDS4", roundID: "dp_2022", year: 2022)
        let wire = PennyMapping.chatContext(context, isNewThread: true)
        #expect(wire.screen?.rawValue == "room_round")
        #expect(wire.multiplayer == true)
        #expect(wire.roomCode == "LEEDS4")
        #expect(wire.roundId == "dp_2022")
        #expect(wire.title == "Same Decision, 2022")
        #expect(context.question == "What are the trade-offs here?")
    }

    @Test func moneyContextsHaveTheirQuestionsAndDefaultTitles() {
        #expect(PennyQuestion.nextMove == "Why this move?")
        #expect(PennyQuestion.why == "Explain this simply")
        #expect(PennyQuestion.testIt == "What does this result mean?")
        #expect(PennyContext(screen: .nextMove, nextMoveID: "mv_1").threadTitle == "Your Next Move")
        #expect(PennyContext(screen: .testIt, nextMoveID: "mv_1").threadTitle == "Test it result")
        #expect(PennyContext(screen: .why, title: "Your deal ends in 165 days").threadTitle == "Your deal ends in 165 days")
        // No context: the server titles the thread from the first message.
        #expect(PennyContext(screen: .money).threadTitle == nil)
        #expect(PennyMapping.chatContext(PennyContext(screen: .testIt), isNewThread: true).screen?.rawValue == "test_it")
    }

    @Test func titleIsCappedAt80Characters() {
        let long = String(repeating: "a", count: 120)
        #expect(PennyContext(screen: .why, title: long).threadTitle?.count == 80)
    }

    // MARK: Requests

    @Test func titleGoesOnlyWithTheFirstMessageOfANewThread() async {
        let log = RequestLog()
        let model = PennyViewModel(
            service: capturingService(log),
            context: .lifeEvent(lifeID: "lf_1", eventID: "ev_1", eventTitle: "Safety fund", age: 19)
        )
        await model.start()
        await model.waitForTurn()
        model.send("And the other option?")
        await model.waitForTurn()
        #expect(log.requests.count == 2)
        #expect(log.requests[0].message == "Which option should I pick?")
        #expect(log.requests[0].threadId == nil)
        #expect(log.requests[0].context?.title == "Safety fund, age 19")
        #expect(log.requests[1].threadId != nil)
        #expect(log.requests[1].context?.title == nil)
        #expect(log.requests[1].context?.eventId == "ev_1")
    }

    @Test func sheetChatSendsTheQuestionAtOnceAndPennyAnswers() async {
        let model = PennyViewModel(
            service: PennyFixtures.scripted(events: PennyFixtures.answerEvents, now: PennyFixtures.now),
            context: .roomRound(roomCode: "LEEDS4", roundID: "dp_1", year: 2022)
        )
        await model.start()
        #expect(model.exchanges.first?.text == "What are the trade-offs here?")
        await model.waitForTurn()
        #expect(model.state.chips.isEmpty)
        #expect(!PennyViewModelTests.groups(model.state).isEmpty)
    }

    // MARK: Chat list and chips

    @Test func emptyThreadsNeverShowInTheChatList() throws {
        let json = """
        {"threads":[
          {"id":"th_1","title":"Safety fund, age 19","updated_at":"2026-10-17T12:00:00Z","message_count":2},
          {"id":"th_2","title":"Chat","updated_at":"2026-10-17T12:00:00Z","message_count":0}
        ]}
        """
        let response = try JSONDecoder().decode(PennyAPI.ThreadsResponse.self, from: Data(json.utf8))
        let rows = PennyMapping.pastThreads(response)
        #expect(rows.map(\.id) == ["th_1"])
        #expect(rows.first?.title == "Safety fund, age 19")
    }

    @Test func starterChipsAreForStudents() {
        #expect(PennyViewModel.chips == [
            "Can I afford a night out this week?",
            "How long will my money last?",
            "Is a Lifetime ISA worth it for me?",
            "How do I make a weekly budget?",
        ])
    }
}
