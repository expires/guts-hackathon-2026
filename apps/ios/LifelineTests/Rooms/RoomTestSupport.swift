import Foundation
@testable import Lifeline

/// Fake WebSocket: the test pushes server messages and reads what the client sent.
final class FakeRoomConnection: RoomConnection, @unchecked Sendable {
    let messages: AsyncStream<RoomWire.Incoming>
    private let continuation: AsyncStream<RoomWire.Incoming>.Continuation
    private let lock = NSLock()
    private var _sent: [RoomWire.Outgoing] = []
    private var _closed = false

    init() {
        (messages, continuation) = AsyncStream<RoomWire.Incoming>.makeStream()
    }

    var sent: [RoomWire.Outgoing] { lock.withLock { _sent } }
    var closed: Bool { lock.withLock { _closed } }

    func send(_ message: RoomWire.Outgoing) async throws {
        lock.withLock { _sent.append(message) }
    }

    func close() async {
        lock.withLock { _closed = true }
        continuation.finish()
    }

    /// Server to client.
    func push(_ message: RoomWire.Incoming) { continuation.yield(message) }

    /// The socket dies (phone sleep, network loss).
    func drop() { continuation.finish() }
}

/// Fake transport: every `connect` makes a new `FakeRoomConnection`.
final class FakeRoomTransport: RoomTransport, @unchecked Sendable {
    private let lock = NSLock()
    private var _connections: [FakeRoomConnection] = []
    private var _failures = 0
    let room: Room

    init(room: Room = RoomTestData.room()) { self.room = room }

    var isMock: Bool { true }
    var connections: [FakeRoomConnection] { lock.withLock { _connections } }
    var latest: FakeRoomConnection? { connections.last }

    /// The next `count` connects throw a network error.
    func failNext(_ count: Int) { lock.withLock { _failures = count } }

    func createRoom(_ request: CreateRoomRequest) async throws -> Room { room }
    func getRoom(code: String) async throws -> Room { room }
    func presets() async throws -> [CharacterSpec] { ContractExamples.characters.presets }
    func life(id: String) async throws -> Life { ContractExamples.life }

    func connect(code: String) async throws -> any RoomConnection {
        try lock.withLock {
            if _failures > 0 {
                _failures -= 1
                throw APIError.network
            }
            let connection = FakeRoomConnection()
            _connections.append(connection)
            return connection
        }
    }
}

enum RoomTestData {
    static func player(_ id: String, _ name: String, host: Bool = false, ready: Bool = false, age: Int? = nil, index: Double? = nil, finished: Bool = false) -> RoomWire.Player {
        .init(id: id, name: name, isHost: host, ready: ready, connected: true, age: age, index: index, finished: finished)
    }

    static func room(status: Room.StatusPayload = .lobby, players: [RoomWire.Player]? = nil) -> Room {
        var room = ContractExamples.room
        room.code = "K7Q2ZP"
        room.mode = .group
        room.maxPlayers = 6
        room.status = status
        room.players = players ?? [player("p1", "Ash", host: true, ready: true)]
        return room
    }

    static func welcome(_ id: String = "p1", room: Room = room()) -> RoomWire.Incoming {
        .init(_type: .welcome, you: room.players.first { $0.id == id }, room: room)
    }
}

/// Waits until `condition` is true or the timeout passes.
@MainActor
func eventually(timeout: Duration = .seconds(3), _ condition: @MainActor () -> Bool) async -> Bool {
    let clock = ContinuousClock()
    let end = clock.now + timeout
    while clock.now < end {
        if condition() { return true }
        try? await Task.sleep(for: .milliseconds(5))
    }
    return condition()
}
