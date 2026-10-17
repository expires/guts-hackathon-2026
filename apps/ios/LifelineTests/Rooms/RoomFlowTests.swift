import Foundation
import Testing
import UIKit
@testable import Lifeline

/// W9: room mapping, links, the mock room with 3 rivals, and the full flow on the mock client.
@MainActor
@Suite("Room flow")
struct RoomFlowTests {
    // MARK: Links

    @Test func parsesJoinLinksAndScans() throws {
        #expect(RoomLink.code(from: try #require(URL(string: "lifeline://join/K7Q2ZP"))) == "K7Q2ZP")
        #expect(RoomLink.code(from: try #require(URL(string: "lifeline://join/k7q2zp"))) == "K7Q2ZP")
        #expect(RoomLink.code(from: try #require(URL(string: "https://example.app/join/LEEDS4"))) == "LEEDS4")
        #expect(RoomLink.code(from: try #require(URL(string: "lifeline://connected?session=1"))) == nil)
        #expect(RoomLink.code(from: try #require(URL(string: "lifeline://join/TOOLONG1"))) == nil)
        #expect(RoomLink.code(fromScanned: " lifeline://join/LEEDS4 ") == "LEEDS4")
        #expect(RoomLink.code(fromScanned: "leeds4") == "LEEDS4")
        #expect(RoomLink.code(fromScanned: "hello world") == nil)
        #expect(RoomLink.normalise("k7-q2 zp!") == "K7Q2ZP")
    }

    @Test func qrFallsBackToLocalImage() {
        // The contract example PNG is only a header, so the app draws the QR itself.
        let png = RoomQR.png(base64: "iVBORw0KGgo=", joinURL: "lifeline://join/K7Q2ZP")
        #expect(png.flatMap(UIImage.init(data:)) != nil)
    }

    // MARK: Mapping

    @Test func lobbyForHostAndGuest() throws {
        let host = RoomFlowFixtures.lobbyHost
        let room = try #require(host.room)
        #expect(room.code == "LEEDS4")
        #expect(host.isHost)
        #expect(host.game?.title == "Money Quiz")
        #expect(host.game?.detail == "6 questions · mixed topics")
        #expect(host.canPickGame)
        #expect(host.startTitle == "Start with 3 players")
        #expect(host.canStart)
        #expect(!host.canReady)
        #expect(host.playersTitle == "Players · 4 of 6")
        #expect(room.players.map(\.statusText) == ["Ready", "Ready", "Ready", "Not ready"])
        #expect(room.qrPNG != nil)
        #expect(host.shareText.contains("lifeline://join/LEEDS4"))
        #expect(host.shareText.contains(Brand.productName))

        let noGame = RoomFlowFixtures.lobbyHostNoGame
        #expect(noGame.game == nil)
        #expect(!noGame.canStart)
        #expect(noGame.startTitle == "Pick a game first")

        let guest = RoomFlowFixtures.lobbyGuest
        #expect(!guest.isHost)
        #expect(!guest.canStart)
        #expect(!guest.canPickGame)
        #expect(guest.canReady)
        #expect(guest.waitingText == "Waiting for Ash to start")

        let reconnecting = RoomFlowFixtures.lobbyReconnecting
        #expect(reconnecting.connection?.text == "Reconnecting (try 2)")
        #expect(!reconnecting.canStart)
    }

    @Test func pickerOptionsPerGame() {
        let quiz = RoomFlowFixtures.pickerQuiz
        #expect(quiz.games.map(\.label) == ["Money Quiz", "Same Decision", "Same Life"])
        #expect(quiz.canConfirm)
        #expect(quiz.confirmTitle == "Pick Money Quiz")

        var draft = GameMapping.Draft()
        draft.game = .sameLife
        draft.quick = true
        draft.pathID = "masters"
        // Master's is not a Quick Life path: the sheet hides it and asks for another.
        let life = GameMapping.picker(draft: draft, paths: MockPlayData.paths, pathsPhase: .ready)
        #expect(!life.paths.contains { $0.id == "masters" })
        #expect(!life.canConfirm)
        draft.pathID = "university"
        let options = draft.options
        #expect(options.pathId == "university")
        #expect(options.quick == true)
        #expect(GameMapping.picker(draft: draft, paths: MockPlayData.paths, pathsPhase: .ready).canConfirm)
    }

    @Test func quizAndDecisionStates() {
        let question = RoomFlowFixtures.quizQuestion
        #expect(question.progressText == "Question 3 of 6")
        #expect(question.choices.count == 3)
        #expect(!question.isLocked)
        #expect(question.deadline != nil)
        #expect(question.duration == 15)

        let reveal = RoomFlowFixtures.quizReveal
        #expect(reveal.isLocked)
        #expect(reveal.deadline == nil)
        #expect(reveal.choices.map(\.mark) == [.wrong, .correct, .none])
        #expect(reveal.reveal?.sourceLabel == "gov.uk · Lifetime ISA")
        #expect(reveal.ranking.first?.name == "Ava")
        #expect(reveal.ranking.first { $0.isMe }?.rank == 2)

        let decision = RoomFlowFixtures.decisionReveal
        #expect(decision.yearText == "2022")
        let lisa = decision.options.first { $0.id == "lisa" }
        #expect(lisa?.mark == .correct)
        #expect(lisa?.pickedBy == ["You", "Ava"])
        #expect(lisa?.gameMoney == 300)
        #expect(decision.missedText == "No answer in time: Jas")
        #expect(decision.pennyLine?.isEmpty == false)

        let over = RoomFlowFixtures.gameOver
        #expect(over.winnerLine == "Ava wins with 230 points")
        #expect(over.isHost)
    }

    @Test func quickLifeCardShowsHabitScore() throws {
        let card = try #require(RoomFlowFixtures.resultQuickLife.quickLife)
        #expect(card.habitOverall == 61)
        #expect(card.habits.count == 6)
        #expect(card.title == "Your Quick Life · University")
        let noScore = GameMapping.quickLife(life: RoomFlowFixtures.life, summary: nil, pathTitle: nil)
        #expect(noScore.habitOverall == nil)
        #expect(noScore.habits.isEmpty)
    }

    @Test func liveShowsAgeOrEvent() {
        let age = RoomFlowFixtures.liveAge
        #expect(age.rivals.rivals.map(\.name) == ["Ash", "Ava", "Tom", "Jas"])
        #expect(age.rivals.rivals.first?.isMe == true)
        #expect(age.rivals.rivals.last?.isConnected == false)
        #expect(age.event == nil)
        #expect(age.ageTitle == "Age up to \(RoomFlowFixtures.life.age + 1)")
        #expect(age.detail == "Age \(RoomFlowFixtures.life.age) · Room LEEDS4")

        let event = RoomFlowFixtures.liveEvent
        #expect(event.ageTitle == nil)
        #expect(event.event?.choices.isEmpty == false)

        let starting = RoomFlowFixtures.liveStarting
        #expect(starting.waitingText == "Starting your life")
        #expect(starting.connection?.kind == .connecting)
    }

    @Test func resultsRankSplitAndRibbons() {
        let state = RoomFlowFixtures.resultFinal
        #expect(state.rows.map(\.name) == ["Ava", "Tom", "Ash", "Jas"])
        #expect(state.winnerLine == "Ava · INDEX 131")
        #expect(state.rows.first { $0.name == "Ava" }?.ribbons == 2)
        #expect(state.rows.first { $0.isMe }?.ribbons == 1)
        #expect(state.rows.first { $0.name == "Jas" }?.ribbonsKnown == false)
        #expect(state.pendingText.isEmpty)
        // Ava fixed for 5 years in 2021. Tom made the same choices, so he has no split.
        #expect(state.splits.count == 1)
        #expect(state.splits.first?.rivalName == "Ava")
        #expect(state.splits.first?.year == 2021)
        #expect(state.splits.first?.myChoice == "Fixed for 2 years at 1.28%.")
        #expect(state.splits.first?.rivalChoice == "Fixed for 5 years at 1.28%.")
        #expect(state.earned.map(\.text) == ["Rate shock survivor"])
        #expect(state.shareText.contains("I came 3 of 4"))

        let pending = RoomFlowFixtures.resultPending
        #expect(pending.pendingText == "2 players still playing")
        #expect(pending.splitsNote == "Other players' choices are not available yet.")
    }

    @Test func resultsCarryRawMoneyForPresentationMode() {
        let state = RoomFlowFixtures.resultFinal
        // Finished rows carry the raw number; the View formats it, so presentation mode can round it.
        #expect(state.rows.allSatisfy { $0.note.isEmpty })
        #expect(state.rows.first?.netWorth == 112_600)
        #expect(state.winnerNetWorth == 112_600)
        #expect(state.winnerNote.isEmpty)

        #expect(RoomAmount.standard(12_534.56, presentation: false) == Money.format(12_534.56))
        #expect(RoomAmount.standard(12_534.56, presentation: true) == Money.format(12_500))
        #expect(RoomAmount.compact(88_449, presentation: true) == Money.compact(88_400))
        #expect(RoomAmount.shown(684, presentation: true) == 680)
        #expect(RoomAmount.spoken(12_534.56, presentation: true) == Money.spoken(12_500))
        #expect(!RoomAmount.standard(4.2, presentation: true).contains("."))
    }

    // MARK: Mock room with 3 rivals

    @Test func mockRoomSimulatesThreeRivals() async throws {
        let transport = MockRoomTransport(client: MockClient(), tick: .milliseconds(5), runYears: 3)
        let room = try await transport.createRoom(.init(mode: .group, hostName: "Ash", presetId: "nurse-leeds", startYear: 2021))
        let session = RoomSession(transport: transport, retryDelays: [.zero], pingInterval: nil)
        await session.open(room: room, name: "Ash")
        #expect(await eventually { session.myPlayerID == "p1" && session.link == .live })
        #expect(await eventually { (session.room?.players.count ?? 0) == 4 && session.room?.players.allSatisfy { $0.ready == true || $0.isHost } == true })
        #expect(session.room?.players.map(\.name) == ["Ash", "Ava", "Tom", "Jas"])

        await session.start()
        #expect(await eventually { session.room?.status == .playing })
        await session.progress(RoomProgress(lifeID: "lf_mock01", age: 30, year: 2022, netWorth: 10_000, index: 101))
        #expect(await eventually { session.room?.players.filter { $0.id != "p1" }.allSatisfy { $0.finished == true } == true })
        #expect(session.room?.status == .playing)

        await session.finish(RoomProgress(lifeID: "lf_mock01", age: 31, year: 2023, netWorth: 12_000, index: 103))
        #expect(await eventually { session.room?.status == .finished })
    }

    /// Regression: every client message through `MockRoomConnection` (exclusive-access crash in `start`).
    @Test func mockConnectionHandlesEveryMessage() async throws {
        for hostIsMe in [true, false] {
            let transport = MockRoomTransport(client: MockClient(), tick: .milliseconds(2), runYears: 2)
            let room = hostIsMe
                ? try await transport.createRoom(.init(mode: .group, hostName: "Ash", presetId: "nurse-leeds", startYear: 2021))
                : try await transport.getRoom(code: "GUEST1")
            let socket = try await transport.connect(code: room.code)
            try await socket.send(.init(_type: .join, name: "Ash"))
            try await socket.send(.init(_type: .ready))
            try await socket.send(.init(_type: .ping))
            try await Task.sleep(for: .milliseconds(30))
            try await socket.send(.init(_type: .start))
            try await socket.send(.init(_type: .progress, lifeId: "lf_mock01", age: 30, year: 2022, netWorth: 1_000, index: 101))
            try await socket.send(.init(_type: .ready))
            try await socket.send(.init(_type: .finish, lifeId: "lf_mock01", age: 31, year: 2023, netWorth: 2_000, index: 102))
            try await socket.send(.init(_type: .leave))
            var types: [RoomWire.Incoming._TypePayload] = []
            let reader = Task {
                var seen: [RoomWire.Incoming._TypePayload] = []
                for await message in socket.messages {
                    seen.append(message._type)
                    if seen.contains(.started), seen.contains(.pong) { break }
                }
                return seen
            }
            try await Task.sleep(for: .milliseconds(200))
            await socket.close()
            types = await reader.value
            #expect(types.first == .welcome)
            #expect(types.contains(.pong))
            #expect(types.contains(.started), "host \(hostIsMe)")
        }
    }

    @Test func mockRoomGuestRejoinsAfterDrop() async throws {
        let transport = MockRoomTransport(client: MockClient(), tick: .seconds(3600))
        let room = try await transport.getRoom(code: "ABC123")
        #expect(room.players.first?.isHost == true)
        let session = RoomSession(transport: transport, retryDelays: [.zero, .zero], pingInterval: nil)
        await session.open(room: room, name: "Ash")
        #expect(await eventually { session.myPlayerID != nil && session.link == .live })
        let id = session.myPlayerID
        let count = session.room?.players.count

        await session.resume()
        #expect(await eventually { session.link == .live })
        #expect(session.myPlayerID == id)
        #expect(session.room?.players.count == count)
    }

    // MARK: Full flow on the mock client

    private func mockFlow(runYears: Int = 2) -> (RoomFlowViewModel, RoomSession, GameSession) {
        let client = MockClient()
        let game = GameSession(client: client)
        let transport = MockRoomTransport(client: client, tick: .milliseconds(5), runYears: runYears)
        let session = RoomSession(transport: transport, retryDelays: [.zero], pingInterval: nil)
        return (RoomFlowViewModel(game: game, session: session, play: MockPlayService()), session, game)
    }

    /// Opens the lobby with no name field and waits for the 3 simulated friends to be ready.
    private func openReadyLobby(_ model: RoomFlowViewModel) async -> Bool {
        await model.openLobby()
        return await eventually {
            model.stage == .lobby && (model.lobbyState?.room?.players.filter(\.isReady).count ?? 0) == 4
        }
    }

    @Test func playWithFriendsOpensLobbyAtOnce() async {
        let (model, session, _) = mockFlow()
        await model.openLobby()
        #expect(model.isPresented)
        #expect(await eventually { session.myPlayerID != nil })
        // The name comes from the account (mock "Ash"), not from a form.
        #expect(session.me?.name == "Ash")
        #expect(model.lobbyState?.room?.code.count == 6)
        #expect(model.lobbyState?.room?.qrPNG != nil)
        #expect(model.lobbyState?.canPickGame == true)
        #expect(model.lobbyState?.canStart == false)
    }

    @Test func moneyQuizFlow() async throws {
        let (model, session, _) = mockFlow()
        #expect(await openReadyLobby(model))
        model.openGamePicker()
        #expect(model.showsGamePicker)
        model.pickerActions.onSelectGame("quiz")
        model.pickerActions.onQuestions(3)
        await model.confirmGame()
        #expect(!model.showsGamePicker)
        #expect(await eventually { model.lobbyState?.game?.title == "Money Quiz" && model.lobbyState?.canStart == true })

        await session.start()
        #expect(await eventually { model.stage == .quiz && session.question != nil })
        let question = try #require(session.question)
        #expect(question.total == 3)
        let correct = try #require(MockPlayData.answers[question.id]?.correct)
        model.roundActions.onAnswer(correct)
        #expect(await eventually { model.quizState?.reveal != nil })
        #expect(model.quizState?.choices.first { $0.id == correct }?.mark == .correct)
        #expect(model.quizState?.ranking.first { $0.isMe }?.lastCorrect == true)
        // Answering twice does nothing.
        await session.answer(choiceID: "a")
        #expect(session.myAnswer == correct)

        #expect(await eventually(timeout: .seconds(5)) { model.stage == .gameOver })
        #expect(model.gameOverState?.ranking.count == 4)
        #expect(model.gameOverState?.winnerLine.isEmpty == false)
    }

    @Test func sameDecisionFlow() async throws {
        let (model, session, _) = mockFlow()
        #expect(await openReadyLobby(model))
        model.openGamePicker()
        model.pickerActions.onSelectGame("same_decision")
        model.pickerActions.onYear(2022)
        await model.confirmGame()
        #expect(await eventually { model.lobbyState?.game?.title == "Same Decision" && model.lobbyState?.canStart == true })

        await session.start()
        #expect(await eventually { model.stage == .decision && session.prompt != nil })
        let prompt = try #require(session.prompt)
        model.roundActions.onAnswer(prompt.options[0].id)
        #expect(await eventually { model.decisionState?.pennyLine != nil })
        let state = try #require(model.decisionState)
        #expect(state.options.allSatisfy { $0.gameMoney != nil })
        #expect(state.options.first { $0.id == prompt.options[0].id }?.pickedBy.contains("You") == true)
        #expect(await eventually(timeout: .seconds(5)) { model.stage == .gameOver })
    }

    @Test func quickLifeSameLifeFlow() async throws {
        let (model, session, game) = mockFlow(runYears: 2)
        #expect(await openReadyLobby(model))
        model.openGamePicker()
        model.pickerActions.onSelectGame("same_life")
        #expect(await eventually { model.pickerState.pathsPhase == .ready })
        model.pickerActions.onPath("university")
        model.pickerActions.onQuick(true)
        await model.confirmGame()
        #expect(await eventually { model.lobbyState?.game?.title == "Same Life" && model.lobbyState?.canStart == true })
        #expect(session.room?.options?.pathId == "university")

        await session.start()
        #expect(await eventually { model.myLifeID != nil && model.stage == .live })
        let life = try #require(game.life)
        #expect(model.liveState?.ageTitle == "Age up to \(life.age + 1)")

        await model.age()
        #expect(model.liveState?.event != nil)
        let event = try #require(game.life?.pendingEvents.first)
        await model.choose(eventID: event.id, choiceID: event.choices[0].id)
        #expect(session.me?.age == game.life?.age)

        await model.finishRun()
        #expect(model.stage == .results)
        #expect(await eventually { session.room?.status == .finished })
        #expect(await eventually { model.resultState?.rows.allSatisfy(\.ribbonsKnown) == true })
        #expect(model.resultState?.quickLife != nil)
        #expect(model.resultState?.rows.count == 4)

        await model.leave()
        #expect(model.stage == .entry)
        #expect(!model.isPresented)
    }

    @Test func sessionIgnoresStaleRevealsAndAnswersOnce() async throws {
        let transport = FakeRoomTransport(room: RoomTestData.room(status: .playing))
        let session = RoomSession(transport: transport, retryDelays: [], pingInterval: nil)
        await session.open(room: transport.room, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome(room: transport.room))
        #expect(await eventually { session.link == .live })
        let question = MockPlayData.questions[0]
        socket.push(.init(_type: .question, question: question))
        #expect(await eventually { session.question?.id == question.id })
        await session.answer(choiceID: "c")
        await session.answer(choiceID: "a")
        let answers = socket.sent.filter { $0._type == .answer }
        #expect(answers.count == 1)
        #expect(answers.first?.questionId == question.id)
        #expect(answers.first?.choiceId == "c")
        // A reveal for another question is ignored.
        socket.push(.init(_type: .quizReveal, quizReveal: .init(questionId: "other", correctChoiceId: "a", explanation: "", sourceLabel: "x", ranking: [])))
        socket.push(.init(_type: .ranking, ranking: [.init(playerId: "p1", name: "Ash", score: 100, rank: 1)]))
        #expect(await eventually { session.ranking.first?.score == 100 })
        #expect(session.quizReveal == nil)
        // A new question clears your answer.
        socket.push(.init(_type: .question, question: MockPlayData.questions[1]))
        #expect(await eventually { session.question?.id == MockPlayData.questions[1].id })
        #expect(session.myAnswer == nil)
    }

    @Test func hostPicksGameWithOptions() async throws {
        let transport = FakeRoomTransport()
        let session = RoomSession(transport: transport, retryDelays: [], pingInterval: nil)
        await session.open(room: transport.room, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome())
        #expect(await eventually { session.link == .live })
        await session.pickGame(.sameDecision, options: .init(startYear: 2008))
        let pick = try #require(socket.sent.last)
        #expect(pick._type == .pickGame)
        #expect(pick.game?.rawValue == "same_decision")
        #expect(pick.options?.startYear == 2008)
        var picked = transport.room
        picked.game = .sameDecision
        socket.push(.init(_type: .gamePicked, room: picked))
        #expect(await eventually { session.room?.game == .sameDecision })
    }

    /// Live mode: rival lives come from `GET /v1/lives/{id}` through the client. One rival's life loads (200),
    /// the other does not exist for this player (404).
    @Test func liveResultsFetchRivalLivesThroughClient() async throws {
        let client = MockClient()
        let rival = try await client.createLife(.init(mode: .preset, startYear: 2021, presetId: "nurse-leeds", roomCode: "K7Q2ZP"))
        let socket = FakeRoomConnection()
        let transport = ClientRoomTransport(client: client) { _ in socket }
        let game = GameSession(client: client)
        let session = RoomSession(transport: transport, retryDelays: [], pingInterval: nil)
        let model = RoomFlowViewModel(game: game, session: session, play: MockPlayService())

        var room = RoomTestData.room(status: .playing, players: [
            RoomTestData.player("p1", "Ash", host: true, ready: true),
            RoomTestData.player("p2", "Ava", ready: true),
            RoomTestData.player("p3", "Tom", ready: true),
        ])
        await session.open(room: room, name: "Ash")
        socket.push(RoomTestData.welcome(room: room))
        #expect(await eventually { session.link == .live && model.myLifeID != nil })
        let mine = try #require(game.life)

        room.status = .finished
        room.players[0].lifeId = mine.id
        room.players[1].lifeId = rival.id
        room.players[2].lifeId = "lf_not_shared"
        for index in room.players.indices {
            room.players[index].finished = true
            room.players[index].index = [104, 131, 99][index]
            room.players[index].netWorth = [88_000, 112_000, 70_000][index]
        }
        socket.push(.init(_type: .finished, room: room))
        #expect(await eventually { model.rivalLives[rival.id] != nil })

        let state = try #require(model.resultState)
        #expect(state.rows.first { $0.name == "Ava" }?.ribbonsKnown == true)
        #expect(state.rows.first { $0.name == "Tom" }?.ribbonsKnown == false)
        #expect(model.rivalLives["lf_not_shared"] == nil)
        // Ava's life loaded and made the same choices as yours.
        #expect(state.splits.isEmpty)
        #expect(state.splitsNote == "Your lives made the same choices.")
    }

    @Test func liveResultsWithOnly404sShowNotAvailable() {
        let room = RoomFlowFixtures.finishedRoom
        let state = RoomMapping.result(room: room, myID: "p1", myLife: RoomFlowFixtures.life, rivalLives: [:], link: .live, isSampleData: false)
        #expect(state.splitsNote == "Other players' choices are not available yet.")
        #expect(state.rows.filter { !$0.isMe }.allSatisfy { !$0.ribbonsKnown })
    }

    /// Play tab Join: scanner, then "Type a code instead", then the room opens.
    @Test func typeCodeInsteadJoins() async {
        let game = GameSession(client: MockClient())
        let model = RoomFlowViewModel(game: game, session: RoomSession(transport: FakeRoomTransport(), retryDelays: [], pingInterval: nil))
        model.openScanner()
        #expect(model.showsScanner)
        model.scannerActions.onTypeCode()
        #expect(!model.showsScanner)
        #expect(await eventually { model.showsCodeEntry })
        model.codeEntryActions.onJoinCodeChange("k7q2zp")
        #expect(model.entryState.canJoin)
        model.codeEntryActions.onJoin()
        #expect(await eventually { model.session.room?.code == "K7Q2ZP" && model.isPresented })
        #expect(!model.showsCodeEntry)
        #expect(!model.showsScanner)
    }

    /// V4 F4-1: leaving the Play tab closes the room covers but keeps the room and the life.
    @Test func otherTabHidesCoversAndKeepsRoomAndLife() async throws {
        let (model, session, game) = mockFlow()
        #expect(await openReadyLobby(model))
        _ = await game.startLife(.init(mode: .preset, startYear: 2021, presetId: "nurse-leeds"))
        let lifeID = try #require(game.life?.id)
        model.openGamePicker()
        model.showsScanner = true
        #expect(model.isPresented && model.showsGamePicker)

        #expect(PlayScreen.closesCovers(for: .penny))
        #expect(PlayScreen.closesCovers(for: .money))
        #expect(!PlayScreen.closesCovers(for: .play))
        model.hideCovers()
        #expect(!model.isPresented)
        #expect(!model.showsGamePicker)
        #expect(!model.showsScanner)
        #expect(!model.showsCodeEntry)
        #expect(session.room != nil)
        #expect(game.life?.id == lifeID)
        #expect(model.entryState.activeRoom != nil)
    }

    @Test func scannedTextJoinsOrHints() async {
        let game = GameSession(client: MockClient())
        let model = RoomFlowViewModel(game: game, session: RoomSession(transport: FakeRoomTransport(), retryDelays: [], pingInterval: nil))
        model.openScanner()
        model.scanned("not a room")
        #expect(model.showsScanner)
        #expect(model.scannerHintText == "That QR code is not a \(Brand.productName) room.")
        model.scanned("lifeline://join/K7Q2ZP")
        #expect(!model.showsScanner)
        #expect(await eventually { model.session.room?.code == "K7Q2ZP" })
        #expect(model.isPresented)
    }
}
