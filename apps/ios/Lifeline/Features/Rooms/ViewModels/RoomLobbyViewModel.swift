import Foundation
import Observation

// Minimal ViewModels created by W6 in the ADR 0011 restructure. W7 owns and extends them
// (WebSocket roster, progress, finish).

/// "Same Life" room lobby: create or join, share the code, wait for players.
@MainActor
@Observable
final class RoomLobbyViewModel {
    private let client: any LifelineClient
    private let playerName: String
    private(set) var room: Room?
    private(set) var phase: LoadPhase = .ready
    private(set) var joinCode = ""
    private(set) var isHost = false
    @ObservationIgnored var onLeave: @MainActor () -> Void = {}
    @ObservationIgnored var onStart: @MainActor (Room) -> Void = { _ in }

    init(client: any LifelineClient, playerName: String = "You") {
        self.client = client
        self.playerName = playerName
    }

    var state: RoomLobbyViewState {
        Self.makeState(room: room, phase: phase, joinCode: joinCode, isHost: isHost, myName: playerName)
    }

    var actions: RoomLobbyActions {
        RoomLobbyActions(
            onCreate: { [weak self] mode in Task { await self?.create(mode: mode) } },
            onJoinCodeChange: { [weak self] in self?.joinCode = String($0.uppercased().filter { $0.isLetter || $0.isNumber }.prefix(6)) },
            onJoin: { [weak self] in Task { await self?.join() } },
            onStart: { [weak self] in
                guard let self, let room else { return }
                onStart(room)
            },
            onLeave: { [weak self] in self?.onLeave() }
        )
    }

    func create(mode: String) async {
        phase = .loading(.init(message: "Making a room"))
        do {
            room = try await client.createRoom(
                .init(
                    mode: CreateRoomRequest.ModePayload(rawValue: mode) ?? .duel,
                    hostName: playerName,
                    presetId: "nurse-leeds",
                    startYear: 2006
                )
            )
            isHost = true
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    func join() async {
        guard joinCode.count == 6 else { return }
        phase = .loading(.init(message: "Joining room \(joinCode)"))
        do {
            room = try await client.getRoom(code: joinCode)
            isHost = false
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    static func modeLabel(_ mode: String) -> String {
        switch mode {
        case "duel": "Duel (2 players)"
        case "group": "Group (up to 8)"
        case "class": "Class (a host runs the room)"
        default: mode.capitalized
        }
    }

    static func makeState(room: Room?, phase: LoadPhase, joinCode: String, isHost: Bool, myName: String) -> RoomLobbyViewState {
        let info = room.map { room in
            RoomLobbyViewState.RoomInfo(
                code: room.code,
                modeLabel: modeLabel(room.mode.rawValue),
                joinURL: room.joinUrl,
                qrPNG: Data(base64Encoded: room.qrPngBase64),
                players: room.players.map { .init(id: $0.id, name: $0.name, isHost: $0.isHost, isMe: $0.name == myName) },
                maxPlayers: room.maxPlayers,
                statusLabel: room.status == .lobby ? "Waiting for players" : room.status.rawValue.capitalized,
                startYear: room.startYear
            )
        }
        return RoomLobbyViewState(
            phase: phase,
            room: info,
            joinCode: joinCode,
            canJoin: joinCode.count == 6,
            isHost: isHost,
            canStart: isHost && (room?.players.count ?? 0) >= 1 && room?.status == .lobby
        )
    }
}

/// Live rival strip. Fed from the room roster.
@MainActor
@Observable
final class RivalStripViewModel {
    private(set) var players: [Components.Schemas.Player]
    let myID: String?

    init(players: [Components.Schemas.Player], myID: String?) {
        self.players = players
        self.myID = myID
    }

    func update(players: [Components.Schemas.Player]) {
        self.players = players
    }

    var state: RivalStripViewState {
        Self.makeState(players: players, myID: myID)
    }

    static func makeState(players: [Components.Schemas.Player], myID: String?) -> RivalStripViewState {
        RivalStripViewState(
            rivals: players.map {
                .init(id: $0.id, name: $0.name, age: $0.age, netWorth: $0.netWorth, index: $0.index, isMe: $0.id == myID, finished: $0.finished ?? false)
            }
        )
    }
}

/// End comparison. Uses fixture data until the room finish message carries per-player results.
@MainActor
@Observable
final class RoomResultViewModel {
    let state: RoomResultViewState
    @ObservationIgnored var onPlayAgain: @MainActor () -> Void = {}
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(state: RoomResultViewState) {
        self.state = state
    }

    var actions: RoomResultActions {
        RoomResultActions(
            onPlayAgain: { [weak self] in self?.onPlayAgain() },
            onClose: { [weak self] in self?.onClose() }
        )
    }
}
