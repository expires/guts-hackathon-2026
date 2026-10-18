import Foundation
import Observation

// Legacy room ViewModels (W6, W7). Kept so W6 fixtures, the Playground and W6/W7 tests compile.
// The W9 room flow uses RoomFlowViewModel, RoomSession and RoomMapping instead.

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
    /// Set by `loadDemo`. Rooms are Tier 2 on the backend, so the Play tab shows this fixture.
    private(set) var demo: RoomDemo?

    init(client: any LifelineClient, playerName: String = "You") {
        self.client = client
        self.playerName = playerName
    }

    var state: RoomLobbyViewState {
        if let demo { return Self.makeDemoState(demo: demo, phase: phase) }
        return Self.makeState(room: room, phase: phase, joinCode: joinCode, isHost: isHost, myName: playerName)
    }

    /// Shows the fixture room (lobby with 4 players).
    func loadDemo(_ demo: RoomDemo) {
        self.demo = demo
        room = demo.lobby
        isHost = true
        phase = .ready
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
        phase = .loading(.init(message: L10n.tr("Making a room")))
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
        phase = .loading(.init(message: L10n.tr("Joining room \(joinCode)")))
        do {
            room = try await client.getRoom(code: joinCode)
            isHost = false
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    /// Lobby state for the fixture room. Every number comes from `RoomDemo`.
    static func makeDemoState(demo: RoomDemo, phase: LoadPhase) -> RoomLobbyViewState {
        let room = demo.lobby
        var state = makeState(room: room, phase: phase, joinCode: "", isHost: true, myName: "You")
        state.room?.players = room.players.map { player in
            let ready = player.lifeId != nil
            return .init(
                id: player.id, name: player.name, isHost: player.isHost, isMe: player.id == demo.myID,
                face: demo.faces[player.id] ?? "face-teen",
                statusText: ready ? L10n.tr("Ready") : L10n.tr("Joining…"),
                isReady: ready
            )
        }
        let startAge = room.gameStartYear - demo.birthYear
        let endYear = room.gameStartYear + demo.years
        state.lifeLine = L10n.tr("\(demo.shortName), \(startAge), \(demo.occupation), \(demo.town). Sep \(String(room.gameStartYear)) to Sep \(String(endYear)). Same events. Your own pace.")
        state.rulesLine = L10n.tr("\(demo.years) years · \(demo.rewindsEach) rewinds each · real rates to \(String(demo.realRatesUntil))")
        state.playersTitle = L10n.tr("Players · \(room.players.count) of \(room.maxPlayers)")
        let ready = room.players.filter { $0.lifeId != nil }.count
        state.startTitle = L10n.tr("Start with \(ready) players")
        state.canStart = ready >= 2
        state.isSampleData = true
        return state
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
                statusLabel: room.status == .lobby ? L10n.tr("Waiting for players") : room.status.rawValue.capitalized,
                startYear: room.gameStartYear
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

/// Live room (Play-Live): the shared life plus the rival strip. Fixture data (Tier 2).
@MainActor
@Observable
final class RoomLiveViewModel {
    let demo: RoomDemo
    @ObservationIgnored var onOpenLesson: @MainActor () -> Void = {}
    @ObservationIgnored var onFinish: @MainActor () -> Void = {}
    @ObservationIgnored var onLeave: @MainActor () -> Void = {}

    init(demo: RoomDemo) {
        self.demo = demo
    }

    var state: RoomLiveViewState { Self.makeState(demo: demo) }

    var actions: RoomLiveActions {
        RoomLiveActions(
            onOpenLesson: { [weak self] in self?.onOpenLesson() },
            onFinish: { [weak self] in self?.onFinish() },
            onLeave: { [weak self] in self?.onLeave() }
        )
    }

    static func makeState(demo: RoomDemo) -> RoomLiveViewState {
        let room = demo.live
        var rivals = RivalStripViewModel.makeState(players: room.players, myID: demo.myID)
        rivals.rivals = rivals.rivals.map { rival in
            var copy = rival
            copy.face = demo.faces[rival.id] ?? "face-teen"
            return copy
        }
        let notes = room.players.filter { $0.id != demo.myID }.compactMap { player in
            demo.notes[player.id].map { "\(player.name): \($0)." }
        }
        return RoomLiveViewState(
            name: demo.characterName,
            face: "face-priya",
            detail: L10n.tr("Age \(demo.story.age) · Room \(room.code)"),
            bank: demo.story.bank,
            rivals: rivals,
            rivalCaption: ([L10n.tr("Age · INDEX.")] + notes).joined(separator: " "),
            storyTitle: L10n.tr("\(String(demo.story.year)) · Age \(demo.story.age)"),
            storyLines: demo.story.lines,
            lessonTitle: L10n.tr("Lesson: \(demo.story.lessonTitle)"),
            stats: [
                .init(id: "happiness", icon: "happiness", title: L10n.tr("Happiness"), value: demo.story.happiness),
                .init(id: "money", icon: "savings", title: L10n.tr("Money"), value: demo.story.money),
            ],
            isSampleData: true
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

    /// Results for the fixture room, ranked by INDEX.
    static func makeState(demo: RoomDemo) -> RoomResultViewState {
        let room = demo.finished
        let ranked = room.players.sorted { ($0.index ?? 0) > ($1.index ?? 0) }
        let rows = ranked.enumerated().map { offset, player in
            RoomResultViewState.Row(
                id: player.id, rank: offset + 1, name: player.name, index: player.index ?? 100,
                netWorth: player.netWorth ?? 0, ribbons: 0, isMe: player.id == demo.myID,
                face: demo.faces[player.id] ?? "face-teen", note: demo.notes[player.id] ?? ""
            )
        }
        let winner = rows.first
        let endYear = room.gameStartYear + demo.years
        let winnerLine = winner.map { L10n.tr("\($0.name) · INDEX \(Int($0.index.rounded()))") } ?? ""
        let me = rows.first { $0.isMe }
        let share = [
            L10n.tr("Same Life room \(room.code): \(winnerLine) won."),
            me.map { L10n.tr("I came \($0.rank) of \(rows.count) with INDEX \(Int($0.index.rounded())).") },
        ].compactMap { $0 }.joined(separator: " ")
        return RoomResultViewState(
            rows: rows,
            splits: [],
            winnerName: winner?.name ?? "",
            subtitle: L10n.tr("\(room.code) · Sep \(String(room.gameStartYear)) to Sep \(String(endYear))"),
            winnerLine: winnerLine,
            winnerNote: winner?.note ?? "",
            earned: demo.earned,
            shareText: share,
            isSampleData: true
        )
    }

    var actions: RoomResultActions {
        RoomResultActions(
            onPlayAgain: { [weak self] in self?.onPlayAgain() },
            onClose: { [weak self] in self?.onClose() }
        )
    }
}
