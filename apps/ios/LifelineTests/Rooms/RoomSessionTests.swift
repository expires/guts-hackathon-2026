import Foundation
import Testing
@testable import Lifeline

/// W9: the room socket session with a fake WebSocket. Ordering, reconnect with `player_id`, offline.
@MainActor
@Suite("Room session")
struct RoomSessionTests {
    private func makeSession(_ transport: FakeRoomTransport, delays: [Duration] = [.zero, .zero]) -> RoomSession {
        RoomSession(transport: transport, retryDelays: delays, pingInterval: nil)
    }

    @Test func joinsThenWelcomeGivesPlayerID() async throws {
        let transport = FakeRoomTransport()
        let session = makeSession(transport)
        await session.open(room: transport.room, name: "Ash")
        let socket = try #require(transport.latest)
        let join = try #require(socket.sent.first)
        #expect(join._type == .join)
        #expect(join.name == "Ash")
        #expect(join.playerId == nil)
        #expect(session.link == .connecting)

        socket.push(RoomTestData.welcome())
        #expect(await eventually { session.link == .live })
        #expect(session.myPlayerID == "p1")
        #expect(session.isHost)
    }

    @Test func appliesMessagesInOrder() async throws {
        let transport = FakeRoomTransport()
        let session = makeSession(transport)
        var started = 0
        session.onStarted = { _ in started += 1 }
        await session.open(room: transport.room, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome())
        let roster = RoomTestData.room(players: [
            RoomTestData.player("p1", "Ash", host: true, ready: true),
            RoomTestData.player("p2", "Ava", ready: true),
        ])
        socket.push(.init(_type: .roster, room: roster))
        var playing = roster
        playing.status = .playing
        socket.push(.init(_type: .started, room: playing))
        socket.push(.init(_type: .rival, player: RoomTestData.player("p2", "Ava", ready: true, age: 30, index: 101)))
        socket.push(.init(_type: .rival, player: RoomTestData.player("p2", "Ava", ready: true, age: 31, index: 104)))
        socket.push(.init(_type: .started, room: playing))

        #expect(await eventually { session.room?.players.first { $0.id == "p2" }?.age == 31 })
        let ava = try #require(session.room?.players.first { $0.id == "p2" })
        #expect(ava.index == 104)
        #expect(session.room?.status == .playing)
        #expect(started == 1)
    }

    @Test func finishedRoomAnnouncesOnce() async throws {
        let transport = FakeRoomTransport()
        let session = makeSession(transport)
        var finished = 0
        session.onFinished = { _ in finished += 1 }
        await session.open(room: transport.room, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome())
        socket.push(.init(_type: .finished, player: RoomTestData.player("p2", "Ava", finished: true)))
        let done = RoomTestData.room(status: .finished, players: [
            RoomTestData.player("p1", "Ash", host: true, finished: true),
            RoomTestData.player("p2", "Ava", finished: true),
        ])
        socket.push(.init(_type: .finished, room: done))
        socket.push(.init(_type: .finished, room: done))
        #expect(await eventually { session.room?.status == .finished })
        try await Task.sleep(for: .milliseconds(20))
        #expect(finished == 1)
    }

    @Test func finishedCarriesWinnerLineAndRanking() async throws {
        let transport = FakeRoomTransport()
        let session = makeSession(transport)
        await session.open(room: transport.room, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome())
        let done = RoomTestData.room(status: .finished, players: [
            RoomTestData.player("p1", "Ash", host: true, finished: true),
            RoomTestData.player("p2", "Ava", finished: true),
        ])
        socket.push(.init(
            _type: .finished, room: done,
            ranking: [.init(playerId: "p2", name: "Ava", score: 131, rank: 1), .init(playerId: "p1", name: "Ash", score: 104, rank: 2)],
            winnerLine: "Ava wins with INDEX 131 and a habit score of 70."
        ))
        #expect(await eventually { session.winnerLine == "Ava wins with INDEX 131 and a habit score of 70." })
        #expect(session.ranking.map(\.playerId) == ["p2", "p1"])
        await session.leave()
        #expect(session.winnerLine == nil)
    }

    @Test func reconnectsAfterDropAndRejoinsWithPlayerID() async throws {
        let transport = FakeRoomTransport()
        let session = makeSession(transport)
        await session.open(room: transport.room, name: "Ash")
        let first = try #require(transport.latest)
        first.push(RoomTestData.welcome())
        #expect(await eventually { session.link == .live })

        // Progress before the drop is sent again after the re-join.
        await session.progress(RoomProgress(lifeID: "lf_1", age: 31, year: 2023, netWorth: 12_000, index: 103))
        first.drop()

        #expect(await eventually { transport.connections.count == 2 })
        let second = try #require(transport.latest)
        #expect(await eventually { !second.sent.isEmpty })
        let rejoin = try #require(second.sent.first)
        #expect(rejoin._type == .join)
        #expect(rejoin.playerId == "p1")
        if case .reconnecting = session.link {} else { Issue.record("Expected reconnecting, got \(session.link)") }

        second.push(RoomTestData.welcome())
        #expect(await eventually { second.sent.contains { $0._type == .progress } })
        let resent = try #require(second.sent.first { $0._type == .progress })
        #expect(resent.lifeId == "lf_1")
        #expect(resent.age == 31)
        #expect(session.link == .live)
    }

    @Test func dropsMessagesFromAnOldConnection() async throws {
        let transport = FakeRoomTransport()
        let session = makeSession(transport)
        await session.open(room: transport.room, name: "Ash")
        let first = try #require(transport.latest)
        first.push(RoomTestData.welcome())
        #expect(await eventually { session.link == .live })
        let oldGeneration = session.currentGeneration

        await session.resume()
        let second = try #require(transport.latest)
        #expect(second !== first)
        #expect(first.closed)

        // A late message from the old socket must not change the room.
        session.receive(.init(_type: .rival, player: RoomTestData.player("p9", "Ghost", age: 99)), generation: oldGeneration)
        #expect(session.room?.players.contains { $0.id == "p9" } == false)

        session.receive(.init(_type: .rival, player: RoomTestData.player("p2", "Ava", age: 30)), generation: session.currentGeneration)
        #expect(session.room?.players.contains { $0.id == "p2" } == true)
    }

    @Test func resumeAfterSleepRejoinsWithPlayerID() async throws {
        let transport = FakeRoomTransport()
        let session = makeSession(transport)
        await session.open(room: transport.room, name: "Ash")
        transport.latest?.push(RoomTestData.welcome())
        #expect(await eventually { session.myPlayerID == "p1" })

        await session.resume()
        #expect(transport.connections.count == 2)
        let rejoin = try #require(transport.latest?.sent.first)
        #expect(rejoin._type == .join)
        #expect(rejoin.playerId == "p1")
        #expect(rejoin.name == "Ash")
    }

    @Test func goesOfflineAfterRetriesThenReconnects() async throws {
        let transport = FakeRoomTransport()
        transport.failNext(3)
        let session = makeSession(transport, delays: [.zero, .zero])
        await session.open(room: transport.room, name: "Ash")
        #expect(await eventually { if case .offline = session.link { true } else { false } })
        #expect(transport.connections.isEmpty)
        #expect(RoomMapping.connection(session.link)?.canRetry == true)

        await session.reconnect()
        #expect(transport.connections.count == 1)
        #expect(transport.latest?.sent.first?._type == .join)
    }

    @Test func leaveSendsLeaveAndClears() async throws {
        let transport = FakeRoomTransport()
        let session = makeSession(transport)
        await session.open(room: transport.room, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome())
        #expect(await eventually { session.link == .live })
        await session.leave()
        #expect(socket.sent.last?._type == .leave)
        #expect(socket.closed)
        #expect(session.room == nil)
        #expect(session.link == .idle)
        // No reconnect after a leave.
        try await Task.sleep(for: .milliseconds(20))
        #expect(transport.connections.count == 1)
    }

    @Test func onlyHostSendsStart() async throws {
        let guestRoom = RoomTestData.room(players: [
            RoomTestData.player("p1", "Ava", host: true, ready: true),
            RoomTestData.player("p2", "Ash"),
        ])
        let transport = FakeRoomTransport(room: guestRoom)
        let session = makeSession(transport)
        await session.open(room: guestRoom, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome("p2", room: guestRoom))
        #expect(await eventually { session.link == .live })
        await session.start()
        #expect(!socket.sent.contains { $0._type == .start })
        await session.ready()
        #expect(socket.sent.last?._type == .ready)
        #expect(socket.sent.last?.playerId == "p2")
    }

    @Test func hostSendsReadyOnceAfterWelcomeInLobby() async throws {
        let room = RoomTestData.room(players: [RoomTestData.player("p1", "Ash", host: true, ready: false)])
        let transport = FakeRoomTransport(room: room)
        let session = makeSession(transport)
        await session.open(room: room, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome(room: room))
        #expect(await eventually { socket.sent.contains { $0._type == .ready } })
        let ready = try #require(socket.sent.first { $0._type == .ready })
        #expect(ready.playerId == "p1")
        #expect(socket.sent.filter { $0._type == .ready }.count == 1)
    }

    @Test func guestOrReadyHostSendsNoReadyOnWelcome() async throws {
        let transport = FakeRoomTransport()
        let session = makeSession(transport)
        await session.open(room: transport.room, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome())
        #expect(await eventually { session.link == .live })
        try await Task.sleep(for: .milliseconds(20))
        #expect(!socket.sent.contains { $0._type == .ready })
    }

    @Test func serverErrorShowsThenClearsOnNextMessage() async throws {
        let transport = FakeRoomTransport()
        let session = makeSession(transport)
        await session.open(room: transport.room, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome())
        #expect(await eventually { session.link == .live })
        socket.push(.init(_type: .error, error: .init(code: "not_host", message: "Only the host can start.", source: "rooms")))
        #expect(await eventually { session.lastError == "Only the host can start." })
        let model = RoomFlowViewModel(game: GameSession(client: MockClient()), session: session)
        #expect(model.lobbyState?.connection?.kind == .error)
        #expect(model.lobbyState?.connection?.text == "Only the host can start.")

        socket.push(.init(_type: .pong))
        try await Task.sleep(for: .milliseconds(20))
        #expect(session.lastError != nil, "A pong does not clear the error")
        socket.push(.init(_type: .roster, room: transport.room))
        #expect(await eventually { session.lastError == nil })
        #expect(model.lobbyState?.connection == nil)
    }

    @Test func serverErrorClearsAfterItsLifetime() async throws {
        let transport = FakeRoomTransport()
        let session = RoomSession(transport: transport, retryDelays: [], pingInterval: nil, errorLifetime: .milliseconds(30))
        await session.open(room: transport.room, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome())
        #expect(await eventually { session.link == .live })
        socket.push(.init(_type: .error, error: .init(code: "bad", message: "Try again.", source: "rooms")))
        #expect(await eventually { session.lastError == "Try again." })
        #expect(await eventually { session.lastError == nil })
    }
}
