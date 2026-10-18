import Foundation
import Testing
@testable import Lifeline

/// PENNY_V3_BUILD.md F5 (W9): Quick Life first in the picker, one tap on a student, no "I'm ready" step for
/// Quick Life, the ready rule kept for Money Quiz, and the join link opening the lobby.
@MainActor
@Suite("Quick Life lobby")
struct QuickLifeLobbyTests {
    private func mockFlow() -> (RoomFlowViewModel, RoomSession) {
        let client = MockClient()
        let transport = MockRoomTransport(client: client, tick: .milliseconds(5), runYears: 2)
        let session = RoomSession(transport: transport, retryDelays: [.zero], pingInterval: nil)
        return (RoomFlowViewModel(game: GameSession(client: client), session: session, play: MockPlayService()), session)
    }

    // MARK: Picker

    @Test func pickerShowsQuickLifeFirst() {
        #expect(GameMapping.pickerGames(showsCutFeatures: false).map(\.id) == ["quick_life", "quiz"])
        #expect(GameMapping.pickerGames(showsCutFeatures: false).map(\.label) == ["Quick Life", "Money Quiz"])
        // Same Decision and the full life are cut: only the flag shows them, below the others.
        #expect(GameMapping.pickerGames(showsCutFeatures: true).map(\.id) == ["quick_life", "quiz", "same_decision", "same_life"])
        #expect(FeatureFlags.showsCutFeatures == false)

        let first = RoomFlowFixtures.pickerGames
        #expect(first.selectedGame == GamePickerViewState.quickLifeID)
        #expect(first.step == .games)
        // Quick Life has no confirm button on the game list: the student tap confirms.
        #expect(!first.showsConfirm)
        #expect(RoomFlowFixtures.pickerQuiz.showsConfirm)

        let students = RoomFlowFixtures.pickerStudents
        #expect(students.step == .students)
        #expect(students.students.map(\.label) == ["Priya", "Amara", "Jordan", "Kai", "Maya"])
    }

    @Test func quickLifeHasNoYearStep() {
        var draft = GameMapping.Draft()
        #expect(draft.isQuickLife)
        draft.startYear = 2001
        draft.quickStudentID = "qs-kai"
        draft.studentPathID = "job18"
        // The year is preset: the server uses its Quick Life default.
        #expect(draft.options.startYear == nil)
        #expect(draft.options.quickStudentId == "qs-kai")
        #expect(draft.options.pathId == "job18")
        #expect(draft.options.quick == true)
    }

    @Test func oneTapOnAStudentPicksQuickLife() async {
        let (model, session) = mockFlow()
        await model.openLobby()
        #expect(await eventually { session.myPlayerID != nil })
        model.openGamePicker()
        #expect(model.pickerState.step == .games)
        model.pickerActions.onSelectGame(GamePickerViewState.quickLifeID)
        #expect(model.pickerState.step == .students)
        #expect(await eventually { model.pickerState.students.count == 5 })
        // Back returns to the game list.
        model.pickerActions.onBack()
        #expect(model.pickerState.step == .games)
        model.pickerActions.onSelectGame(GamePickerViewState.quickLifeID)

        await model.pickStudent("qs-jordan")
        #expect(!model.showsGamePicker)
        #expect(await eventually { session.room?.options?.quickStudentId == "qs-jordan" })
        #expect(session.room?.game == .sameLife)
        #expect(session.room?.options?.quick == true)
        #expect(session.room?.options?.pathId == "apprentice")
        #expect(session.room?.options?.startYear == nil)
        #expect(model.lobbyState?.game?.title == "Quick Life")
        #expect(model.lobbyState?.game?.detail == "Quick Life, ages 18 to 25 · everyone plays Jordan")
    }

    // MARK: Lobby rules

    @Test func quickLifeStartsAtTwoPlayersWithoutReady() throws {
        var room = RoomFlowFixtures.quickLifeRoom
        room.players = [room.players[0], room.players[3]]
        #expect(room.players[1].ready == false)

        let host = RoomFlowFixtures.lobby(room: room)
        #expect(host.canStart)
        #expect(host.startTitle == "Start with 2 players")
        #expect(try #require(host.room).players.allSatisfy(\.isReady))

        let guest = RoomFlowFixtures.lobby(room: room, myID: "p4")
        #expect(!guest.canReady)
        #expect(guest.isMeReady)
        #expect(guest.waitingText == "Waiting for Ash to start")

        // The host alone cannot start.
        room.players = [room.players[0]]
        let alone = RoomFlowFixtures.lobby(room: room)
        #expect(!alone.canStart)
        #expect(alone.startTitle == "Waiting for players")

        // No game yet in a "Play with friends" lobby: Quick Life rules, so no ready button either.
        var empty = RoomFlowFixtures.quickLifeRoom
        empty.game = nil
        empty.options = nil
        let waiting = RoomFlowFixtures.lobby(room: empty, myID: "p4")
        #expect(!waiting.canReady)
        #expect(waiting.waitingText == "Waiting for Ash to pick a game")
        #expect(!RoomFlowFixtures.lobby(room: empty).canStart)
    }

    @Test func moneyQuizStillNeedsEveryoneReady() {
        var room = RoomFlowFixtures.quizRoom
        room.presetId = nil
        let host = RoomFlowFixtures.lobby(room: room)
        #expect(!host.canStart)
        #expect(host.startTitle == "Waiting for 1 to get ready")
        let guest = RoomFlowFixtures.lobby(room: room, myID: "p4")
        #expect(guest.canReady)
        room.players[3].ready = true
        #expect(RoomFlowFixtures.lobby(room: room).canStart)
        // A preset room with no game keeps the ready step (server `_is_quick_life` is false there).
        #expect(RoomMapping.joiningCountsAsReady(RoomFlowFixtures.lobbyRoom) == false)
        #expect(RoomFlowFixtures.lobbyGuest.canReady)
    }

    @Test func guestNeverSendsReadyInQuickLife() async {
        let (model, session) = mockFlow()
        // A friend's lobby: the simulated host picks Quick Life and starts without a "ready" from you.
        await model.join(code: "1234")
        #expect(model.isPresented)
        #expect(await eventually { model.stage == .lobby && session.myPlayerID != nil })
        #expect(model.lobbyState?.canReady == false)
        #expect(await eventually { model.lobbyState?.game?.title == "Quick Life" })
        #expect(await eventually(timeout: .seconds(5)) { session.room?.status == .playing })
        #expect(session.me?.isHost == false)
    }

    @Test func liveRoomHidesOpenInLifeTab() {
        // The full Life game is cut (PENNY_V3_BUILD.md F2): no "Open in the Life tab" unless the flag is on.
        #expect(RoomFlowFixtures.liveAge.canOpenLife == FeatureFlags.showsCutFeatures)
        #expect(!RoomFlowFixtures.liveAge.canOpenLife)
    }

    // MARK: Join link

    @Test func joinLinkOpensTheLobby() async throws {
        let (model, session) = mockFlow()
        let url = try #require(URL(string: RoomLink.joinURL(code: "1234")))
        #expect(url.absoluteString == "lifeline://join/1234")
        // The lobby QR encodes the join link from the room (`join_url`).
        #expect(RoomLink.code(fromScanned: url.absoluteString) == "1234")

        let router = AppRouter(session: GameSession(client: MockClient()))
        router.selection = .money
        #expect(router.handle(url: url))
        #expect(router.join?.code == "1234")
        #expect(!router.handle(url: try #require(URL(string: "lifeline://connected?session=1"))))
        // Switching to Play keeps the room cover; any other tab hides it.
        #expect(!PlayScreen.closesCovers(for: .play))

        // RootScreen then selects Play and calls the shared room flow's join: the cover opens on the lobby.
        await model.join(code: "1234")
        #expect(model.isPresented)
        #expect(await eventually { model.stage == .lobby })
        #expect(session.room?.code == "1234")
        #expect(model.lobbyState?.room?.joinURL == "lifeline://join/1234")
        // The same link again (the camera scanned twice) keeps the room and shows the cover.
        model.isPresented = false
        await model.join(code: "1234")
        #expect(model.isPresented)
        #expect(session.room?.code == "1234")
    }
}
