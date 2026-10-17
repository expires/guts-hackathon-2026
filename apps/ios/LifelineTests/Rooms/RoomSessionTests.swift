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
}
