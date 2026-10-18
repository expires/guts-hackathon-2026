import Foundation

// Same Life rooms: transport layer (W9, ADR 0029 item 3, ADR 0037).
// The room ViewModels talk only to `RoomTransport`. Live mode uses the BOSS-owned `RoomSocket`.
// Mock mode uses `MockRoomTransport`: timed rivals plus rival lives for the end comparison.

/// Wire types from the contract (`x-websocket` on `/v1/rooms/{code}`).
enum RoomWire {
    typealias Outgoing = Components.Schemas.WsClientMessage
    typealias Incoming = Components.Schemas.WsServerMessage
    typealias Player = Components.Schemas.Player
}

/// One open WebSocket to a room. The stream finishes when the socket closes or fails.
/// A connection never reconnects by itself: `RoomSession` opens a new one and re-joins with `player_id`.
protocol RoomConnection: Sendable {
    var messages: AsyncStream<RoomWire.Incoming> { get }
    func send(_ message: RoomWire.Outgoing) async throws
    func close() async
}

/// Everything a Same Life room needs from the backend.
protocol RoomTransport: Sendable {
    /// True when the data is simulated. Screens then show "Mock data".
    var isMock: Bool { get }
    func createRoom(_ request: CreateRoomRequest) async throws -> Room
    func getRoom(code: String) async throws -> Room
    /// Preset characters for the create form (`GET /v1/characters`).
    func presets() async throws -> [CharacterSpec]
    /// Opens the room WebSocket. The caller sends `join` first.
    func connect(code: String) async throws -> any RoomConnection
    /// Another player's life, for the end comparison (ribbons, where the lives split).
    func life(id: String) async throws -> Life
}

enum RoomTransportError: Error, Equatable {
    /// The live WebSocket client is not in the app yet.
    case socketUnavailable

    var apiError: APIError {
        .server(status: 501, code: "not_implemented", message: L10n.tr("Live rooms are not available in this build yet."), source: "rooms")
    }
}

/// REST through `LifelineClient`. The socket comes from `connector`.
struct ClientRoomTransport: RoomTransport {
    let client: any LifelineClient
    let connector: @Sendable (String) async throws -> any RoomConnection

    var isMock: Bool { client.kind == .mock }

    func createRoom(_ request: CreateRoomRequest) async throws -> Room { try await client.createRoom(request) }
    func getRoom(code: String) async throws -> Room { try await client.getRoom(code: code) }
    func presets() async throws -> [CharacterSpec] { try await client.listCharacters(seed: nil).presets }
    func connect(code: String) async throws -> any RoomConnection { try await connector(code) }
    func life(id: String) async throws -> Life { try await client.getLife(id: id) }
}

@MainActor
enum RoomTransportFactory {
    /// Mock client: simulated room with 3 rivals. Live client: REST now, socket when BOSS adds `RoomSocket`.
    static func make(client: any LifelineClient) -> any RoomTransport {
        if client.kind == .mock { return MockRoomTransport(client: client) }
        return ClientRoomTransport(client: client) { code in try await client.roomSocket(code: code) }
    }
}

/// BOSS's WebSocket wrapper (Networking/RoomSocket.swift) has the same shape: messages, send, close.
extension RoomSocket: RoomConnection {}

/// Room codes from deep links (`lifeline://join/1234`), join URLs and QR text.
/// A room code is 4 digits, easy to read aloud (ADR 0064).
enum RoomLink {
    static let codeLength = 4

    /// Digits only, at most 4.
    static func normalise(_ text: String) -> String {
        String(text.filter { $0.isASCII && $0.isNumber }.prefix(codeLength))
    }

    static func isValid(_ code: String) -> Bool {
        code.count == codeLength && code.allSatisfy { $0.isASCII && $0.isNumber }
    }

    /// `lifeline://join/CODE`, `https://host/join/CODE`.
    static func code(from url: URL) -> String? {
        var parts = url.pathComponents.filter { $0 != "/" }
        if url.scheme == "lifeline", let host = url.host() { parts.insert(host, at: 0) }
        guard let index = parts.firstIndex(of: "join"), index + 1 < parts.count else { return nil }
        let code = parts[index + 1]
        return isValid(code) ? code : nil
    }

    /// Text from a QR code: a join link or a bare code.
    static func code(fromScanned text: String) -> String? {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if let url = URL(string: trimmed), url.scheme != nil { return code(from: url) }
        return isValid(trimmed) ? trimmed : nil
    }

    static func joinURL(code: String) -> String { "lifeline://join/\(code)" }
}

/// Circle codes: 6 letters or digits (`JoinCircleRequest.code`).
enum CircleCode {
    static func normalise(_ text: String) -> String {
        String(text.uppercased().filter { $0.isASCII && ($0.isLetter || $0.isNumber) }.prefix(6))
    }

    static func isValid(_ code: String) -> Bool { code.count == 6 && normalise(code) == code }
}

extension Room {
    /// History year of the game: the room's year, else the picked options' year, else 2021.
    /// A lobby has no year until the host picks a game (ADR 0059).
    var gameStartYear: Int { startYear ?? options?.startYear ?? 2021 }
}
