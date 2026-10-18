import Foundation

/// Simulated Same Life room for mock mode, the Playground and UI tests.
/// REST calls go to the mock client. A local "server" plays 3 rivals (Ava, Tom, Jas; 1 rival in a duel):
/// they join, get ready, then age one year at a time until the run ends.
/// Every rival number is simulated and every room screen shows "Mock data".
final class MockRoomTransport: RoomTransport {
    let client: any LifelineClient
    /// Time between simulation steps.
    let tick: Duration
    /// Years each rival plays before it finishes.
    let runYears: Int
    private let registry = MockRoomRegistry()

    var isMock: Bool { true }

    init(client: any LifelineClient, tick: Duration = .milliseconds(1400), runYears: Int = 10) {
        self.client = client
        self.tick = tick
        self.runYears = runYears
    }

    func createRoom(_ request: CreateRoomRequest) async throws -> Room {
        var room = try await client.createRoom(request)
        room.code = await registry.freeCode(seed: room.seed)
        // Lobby first (ADR 0059): the mode follows the player count at start.
        if request.mode == nil { room.mode = .group }
        room.maxPlayers = request.mode == .duel ? 2 : 6
        room.joinUrl = RoomLink.joinURL(code: room.code)
        let age = await startAge(presetID: room.presetId, startYear: room.gameStartYear)
        return await registry.server(code: room.code) {
            MockRoomServer(room: room, hostIsMe: true, startAge: age, tick: tick, runYears: runYears)
        }.snapshot()
    }

    func getRoom(code: String) async throws -> Room {
        if let server = await registry.existing(code: code) { return await server.snapshot() }
        var room = try await client.getRoom(code: code)
        room.code = code
        room.mode = .group
        room.maxPlayers = 6
        room.joinUrl = RoomLink.joinURL(code: code)
        // A friend's "Play with friends" lobby has no preset (ADR 0059): Quick Life rules, no "ready" step.
        room.presetId = nil
        // A rival hosts a room you join.
        room.players = [.init(id: "p2", name: MockRoomServer.rivalNames[0], isHost: true, ready: true, connected: true, finished: false)]
        let age = await startAge(presetID: room.presetId, startYear: room.gameStartYear)
        let joined = room
        return await registry.server(code: code) {
            MockRoomServer(room: joined, hostIsMe: false, startAge: age, tick: tick, runYears: runYears)
        }.snapshot()
    }

    func presets() async throws -> [CharacterSpec] {
        try await client.listCharacters(seed: nil).presets
    }

    func connect(code: String) async throws -> any RoomConnection {
        guard let server = await registry.existing(code: code) else {
            throw APIError.server(status: 404, code: "not_found", message: "That room does not exist.", source: "mock")
        }
        return await server.connect()
    }

    func life(id: String) async throws -> Life {
        guard let server = await registry.server(forRivalLife: id) else { return try await client.getLife(id: id) }
        guard let mine = await server.myLifeID else {
            throw APIError.server(status: 404, code: "not_found", message: "That life is not ready yet.", source: "mock")
        }
        let base = try await client.getLife(id: mine)
        guard let life = await server.rivalLife(id: id, base: base) else { return base }
        return life
    }

    private func startAge(presetID: String?, startYear: Int) async -> Int {
        guard let presetID else { return 18 }
        let presets = (try? await presets()) ?? []
        guard let preset = presets.first(where: { $0.id == presetID }) else { return 30 }
        return max(18, startYear - preset.birthYear)
    }
}

/// One mock server per room code.
actor MockRoomRegistry {
    private var servers: [String: MockRoomServer] = [:]

    func existing(code: String) -> MockRoomServer? { servers[code] }

    /// A 4-digit code no other mock room uses (ADR 0064).
    func freeCode(seed: Int) -> String {
        var number = abs(seed) % 10_000
        while servers[String(format: "%04d", number)] != nil { number = (number + 1) % 10_000 }
        return String(format: "%04d", number)
    }

    func server(code: String, make: () -> MockRoomServer) -> MockRoomServer {
        if let server = servers[code] { return server }
        let server = make()
        servers[code] = server
        return server
    }

    func server(forRivalLife id: String) async -> MockRoomServer? {
        for server in servers.values where await server.hasRivalLife(id) { return server }
        return nil
    }
}

/// A connection to the mock server.
struct MockRoomConnection: RoomConnection {
    let id: Int
    let messages: AsyncStream<RoomWire.Incoming>
    let server: MockRoomServer

    func send(_ message: RoomWire.Outgoing) async throws {
        try await server.receive(message, from: id)
    }

    func close() async {
        await server.disconnect(id)
    }
}

/// The simulated room server. It follows the contract flow: join, roster, ready, start, progress, finish.
actor MockRoomServer {
    static let rivalNames = ["Ava", "Tom", "Jas"]

    private struct Rival {
        var id: String
        var rng: SplitMix64
        /// The rival ages on steps where `step % pace == 0`.
        var pace: Int
    }

    private(set) var room: Room
    private let hostIsMe: Bool
    private let startAge: Int
    private let tick: Duration
    private let runYears: Int
    private var rivals: [Rival] = []
    private var myPlayerID: String?
    private(set) var myLifeID: String?
    private var connections: [Int: AsyncStream<RoomWire.Incoming>.Continuation] = [:]
    private var nextConnection = 1
    private var step = 0
    /// Guest mode: steps the simulated host waits after its Quick Life pick before it starts.
    private var lobbyWait = 0
    private var simulation: Task<Void, Never>?
    // Games: Money Quiz and Same Decision rounds.
    private var round = -1
    private var roundOpen = false
    private var roundTicks = 0
    private var answers: [String: String] = [:]
    private var answerOrder: [String] = []
    private var scores: [String: Int] = [:]
    private var lastCorrect: [String: Bool] = [:]

    init(room: Room, hostIsMe: Bool, startAge: Int, tick: Duration, runYears: Int) {
        self.room = room
        self.hostIsMe = hostIsMe
        self.startAge = startAge
        self.tick = tick
        self.runYears = runYears
        let count = room.mode == .duel ? 1 : Self.rivalNames.count
        rivals = (0..<count).map { offset in
            Rival(id: "p\(offset + 2)", rng: SplitMix64(seed: UInt64(room.seed) &+ UInt64(offset) &* 7919), pace: [1, 2, 1][offset])
        }
        if hostIsMe {
            self.room.players = room.players.map { player in
                var copy = player
                copy.connected = false
                return copy
            }
        }
    }

    func snapshot() -> Room { room }

    func hasRivalLife(_ id: String) -> Bool { rivals.contains { Self.lifeID(rival: $0.id) == id } }

    // MARK: Connections

    func connect() -> MockRoomConnection {
        let (stream, continuation) = AsyncStream<RoomWire.Incoming>.makeStream()
        let id = nextConnection
        nextConnection += 1
        connections[id] = continuation
        return MockRoomConnection(id: id, messages: stream, server: self)
    }

    func disconnect(_ id: Int) {
        connections.removeValue(forKey: id)?.finish()
        if connections.isEmpty, let me = myPlayerID {
            update(me) { $0.connected = false }
        }
    }

    /// Closes every socket, as when the phone sleeps. The client must re-join with its `player_id`.
    func dropAll() {
        for continuation in connections.values { continuation.finish() }
        connections.removeAll()
        if let me = myPlayerID { update(me) { $0.connected = false } }
    }

    func receive(_ message: RoomWire.Outgoing, from connection: Int) throws {
        switch message._type {
        case .join: join(message, connection: connection)
        case .ready:
            guard let me = myPlayerID else { return }
            update(me) { $0.ready = true }
            broadcast(.init(_type: .roster, room: room))
        case .start:
            guard hostIsMe, room.status == .lobby else { return }
            start()
        case .progress:
            guard let me = myPlayerID else { return }
            myLifeID = message.lifeId ?? myLifeID
            update(me) { player in
                player.lifeId = message.lifeId ?? player.lifeId
                player.age = message.age ?? player.age
                player.year = message.year ?? player.year
                player.netWorth = message.netWorth ?? player.netWorth
                player.index = message.index ?? player.index
            }
            if let player = player(me) { broadcast(.init(_type: .rival, player: player)) }
        case .finish:
            guard let me = myPlayerID else { return }
            update(me) { player in
                player.finished = true
                player.netWorth = message.netWorth ?? player.netWorth
                player.index = message.index ?? player.index
                player.age = message.age ?? player.age
                player.year = message.year ?? player.year
            }
            if let player = player(me) { broadcast(.init(_type: .finished, player: player)) }
            finishIfDone()
        case .leave:
            guard let me = myPlayerID else { return }
            update(me) { $0.connected = false }
            broadcast(.init(_type: .roster, room: room))
        case .ping:
            connections[connection]?.yield(.init(_type: .pong))
        case .pickGame:
            guard hostIsMe, room.status == .lobby, let raw = message.game?.rawValue else { return }
            pick(game: raw, options: message.options ?? .init())
        case .answer:
            guard let me = myPlayerID, roundOpen, answers[me] == nil, let choice = message.choiceId else { return }
            answers[me] = choice
            answerOrder.append(me)
        }
    }

    private func pick(game: String, options: PlayWire.Options) {
        room.game = Room.GamePayload(rawValue: game)
        room.options = options
        if let year = options.startYear { room.startYear = year }
        broadcast(.init(_type: .gamePicked, room: room))
    }

    private func join(_ message: RoomWire.Outgoing, connection: Int) {
        let id: String
        if let resume = message.playerId, room.players.contains(where: { $0.id == resume }) {
            id = resume
        } else if hostIsMe, myPlayerID == nil, let host = room.players.first(where: { $0.isHost }) {
            id = host.id
        } else {
            id = "p\(room.players.count + rivals.count + 1)"
            room.players.append(.init(id: id, name: "Player \(room.players.count + 1)", isHost: false, ready: false, connected: true, finished: false))
        }
        myPlayerID = id
        update(id) { player in
            player.connected = true
            if let name = message.name, !name.isEmpty { player.name = name }
        }
        guard let me = player(id) else { return }
        connections[connection]?.yield(.init(_type: .welcome, you: me, room: room))
        broadcast(.init(_type: .roster, room: room))
        startSimulation()
    }

    // MARK: Simulation

    private func startSimulation() {
        guard simulation == nil else { return }
        let tick = tick
        simulation = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: tick)
                guard let self, await self.advance() else { return }
            }
        }
    }

    /// One simulation step. Returns false when the room is over.
    func advance() -> Bool {
        step += 1
        switch room.status {
        case .lobby: advanceLobby()
        case .playing: advancePlaying()
        case .finished: return false
        }
        return true
    }

    private func advanceLobby() {
        if let next = rivals.first(where: { rival in !room.players.contains { $0.id == rival.id } }) {
            let index = rivals.firstIndex { $0.id == next.id } ?? 0
            room.players.append(.init(id: next.id, name: Self.rivalNames[index], isHost: false, ready: false, connected: true, finished: false))
            broadcast(.init(_type: .roster, room: room))
        } else if let waiting = room.players.first(where: { $0.id != myPlayerID && $0.ready != true }) {
            update(waiting.id) { $0.ready = true }
            broadcast(.init(_type: .roster, room: room))
        } else if !hostIsMe, RoomMapping.joiningCountsAsReady(room) {
            // "Play with friends" room: the simulated host picks Quick Life, waits a few steps so the guest
            // sees the lobby, then starts. Joining counts as ready: the guest never sends "ready".
            if room.game == nil, let student = MockPlayData.quickStudents.first {
                pick(game: RoomGameKind.sameLife.rawValue, options: .init(pathId: student.pathId, quick: true, quickStudentId: student.id))
                lobbyWait = 3
            } else if lobbyWait > 0 {
                lobbyWait -= 1
            } else {
                start()
            }
        } else if !hostIsMe, room.players.allSatisfy({ $0.ready == true }) {
            // Preset room: the simulated host picks a short Money Quiz once everyone is ready, then starts.
            if room.game == nil {
                pick(game: RoomGameKind.quiz.rawValue, options: .init(questions: 4, topic: .mixed))
            } else {
                start()
            }
        }
    }

    private func start() {
        // Server rule (routes/rooms.py "start"): in a Quick Life round the host's Start counts every seated player as ready.
        if RoomMapping.joiningCountsAsReady(room) {
            for index in room.players.indices { room.players[index].ready = true }
        }
        room.status = .playing
        room.mode = room.players.count == 2 ? .duel : .group
        switch RoomGameKind(room: room.game) {
        case .quiz, .sameDecision:
            for player in room.players { scores[player.id] = 0 }
            broadcast(.init(_type: .started, room: room))
            openRound(0)
            return
        case .sameLife, nil:
            break
        }
        for rival in rivals {
            update(rival.id) { player in
                player.lifeId = Self.lifeID(rival: rival.id)
                player.age = startAge
                player.year = room.gameStartYear
                player.netWorth = 9_000
                player.index = 100
                player.finished = false
            }
        }
        broadcast(.init(_type: .started, room: room))
    }

    private func advancePlaying() {
        switch RoomGameKind(room: room.game) {
        case .quiz, .sameDecision:
            advanceRound()
            return
        case .sameLife, nil:
            break
        }
        for offset in rivals.indices {
            let id = rivals[offset].id
            guard let player = player(id), player.finished != true, step % rivals[offset].pace == 0 else { continue }
            let worth = Double(rivals[offset].rng.next(in: -2_500...8_500))
            let index = Double(rivals[offset].rng.next(in: -4...6))
            update(id) { player in
                player.age = (player.age ?? startAge) + 1
                player.year = (player.year ?? room.gameStartYear) + 1
                player.netWorth = ((player.netWorth ?? 0) + worth).rounded()
                player.index = (player.index ?? 100) + index
                if (player.year ?? 0) >= room.gameStartYear + runYears { player.finished = true }
            }
            guard let updated = self.player(id) else { continue }
            broadcast(.init(_type: updated.finished == true ? .finished : .rival, player: updated))
        }
        finishIfDone()
    }

    private func finishIfDone() {
        guard room.status == .playing, room.players.allSatisfy({ $0.finished == true }) else { return }
        room.status = .finished
        // Ranking by result: INDEX, then game net worth.
        let ranked = room.players.sorted { ($0.index ?? 0, $0.netWorth ?? 0) > ($1.index ?? 0, $1.netWorth ?? 0) }
        let ranking = ranked.enumerated().map { offset, player in
            PlayWire.Score(playerId: player.id, name: player.name, score: Int((player.index ?? 0).rounded()), rank: offset + 1)
        }
        let winner = ranked.first
        let line = winner.map { "\($0.name) wins this Same Life with INDEX \(Int(($0.index ?? 0).rounded())). Same events, better choices." }
        broadcast(.init(_type: .finished, room: room, ranking: ranking, winnerLine: line))
        simulation?.cancel()
    }

    // MARK: Rounds (Money Quiz, Same Decision)

    private var isQuiz: Bool { RoomGameKind(room: room.game) == .quiz }

    private var roundCount: Int {
        isQuiz ? min(room.options?.questions ?? 6, MockPlayData.questions.count) : MockPlayData.prompts.count
    }

    private func openRound(_ index: Int) {
        round = index
        roundOpen = true
        roundTicks = 0
        answers = [:]
        answerOrder = []
        if isQuiz {
            var question = MockPlayData.questions[index]
            question.index = index
            question.total = roundCount
            broadcast(.init(_type: .question, question: question))
        } else {
            broadcast(.init(_type: .decision, decision: MockPlayData.prompts[index]))
        }
    }

    private func advanceRound() {
        roundTicks += 1
        guard roundOpen else {
            // Two steps to read the reveal, then the next round or the end.
            if roundTicks >= 2 {
                if round + 1 < roundCount { openRound(round + 1) } else { endGame() }
            }
            return
        }
        // One rival answers per step. Rivals are right about two times in three.
        if let offset = rivals.firstIndex(where: { answers[$0.id] == nil }) {
            let id = rivals[offset].id
            let roll = rivals[offset].rng.next(in: 0...2)
            answers[id] = roll == 0 ? wrongChoice() : bestChoice()
            answerOrder.append(id)
        }
        let everyone = room.players.allSatisfy { answers[$0.id] != nil || $0.connected == false }
        if everyone || roundTicks >= 8 { reveal() }
    }

    private func bestChoice() -> String {
        if isQuiz { return MockPlayData.answers[MockPlayData.questions[round].id]?.correct ?? "a" }
        return MockPlayData.outcomes[MockPlayData.prompts[round].id]?.best ?? ""
    }

    private func wrongChoice() -> String {
        let ids = isQuiz ? MockPlayData.questions[round].choices.map(\.id) : MockPlayData.prompts[round].options.map(\.id)
        return ids.first { $0 != bestChoice() } ?? bestChoice()
    }

    private func reveal() {
        roundOpen = false
        roundTicks = 0
        if isQuiz {
            let question = MockPlayData.questions[round]
            let answer = MockPlayData.answers[question.id]
            for player in room.players {
                let correct = answers[player.id] == answer?.correct
                lastCorrect[player.id] = correct
                // 100 for a right answer, plus a small bonus for the first answers.
                let order = answerOrder.firstIndex(of: player.id) ?? answerOrder.count
                if correct { scores[player.id, default: 0] += 100 + max(0, 30 - 10 * order) }
            }
            broadcast(.init(_type: .quizReveal, quizReveal: .init(
                questionId: question.id, correctChoiceId: answer?.correct ?? "",
                explanation: answer?.line ?? "", sourceLabel: question.sourceLabel, sourceUrl: question.sourceUrl,
                ranking: ranking()
            )))
        } else {
            let prompt = MockPlayData.prompts[round]
            guard let result = MockPlayData.outcomes[prompt.id] else { return }
            let changes = Dictionary(uniqueKeysWithValues: result.outcomes.map { ($0.optionId, $0.gameMoneyChange) })
            for player in room.players {
                let choice = answers[player.id]
                let points = choice == result.best ? 100 : ((changes[choice ?? ""] ?? -1) > 0 ? 50 : 0)
                scores[player.id, default: 0] += points
                lastCorrect[player.id] = choice == result.best
            }
            broadcast(.init(_type: .decisionReveal, decisionReveal: .init(
                promptId: prompt.id,
                choices: room.players.map { .init(playerId: $0.id, name: $0.name, optionId: answers[$0.id]) },
                outcomes: result.outcomes, pennyLine: result.line, ranking: ranking()
            )))
        }
    }

    private func ranking() -> [PlayWire.Score] {
        room.players
            .sorted { (scores[$0.id] ?? 0, $1.name) > (scores[$1.id] ?? 0, $0.name) }
            .enumerated()
            .map { offset, player in
                .init(playerId: player.id, name: player.name, score: scores[player.id] ?? 0, rank: offset + 1, lastCorrect: lastCorrect[player.id])
            }
    }

    private func endGame() {
        room.status = .finished
        for index in room.players.indices { room.players[index].finished = true }
        broadcast(.init(_type: .finished, room: room, ranking: ranking()))
        simulation?.cancel()
    }

    // MARK: Rival lives (end comparison)

    /// A rival's life: your life with different choices in some years. Simulated (mock mode only).
    func rivalLife(id: String, base: Life) -> Life? {
        guard let offset = rivals.firstIndex(where: { Self.lifeID(rival: $0.id) == id }),
              let player = player(rivals[offset].id) else { return nil }
        var life = base
        life.id = id
        life.finances.netWorth = player.netWorth ?? base.finances.netWorth
        life.index.value = player.index ?? base.index.value
        life.ribbons = Array(base.ribbons.prefix(offset + 1))
        let choices = ContractExamples.event.choices
        var decisions = 0
        life.history = base.history.map { entry in
            guard let choiceID = entry.choiceId else { return entry }
            decisions += 1
            // Rival N takes the other path at its N-th decision.
            guard decisions == offset + 1, let other = choices.first(where: { $0.id != choiceID }) else { return entry }
            var copy = entry
            copy.choiceId = other.id
            copy.text = other.label
            return copy
        }
        return life
    }

    // MARK: Helpers

    static func lifeID(rival: String) -> String { "lf_rival_\(rival)" }

    private func player(_ id: String) -> RoomWire.Player? { room.players.first { $0.id == id } }

    /// Copies the player, changes the copy, then writes it back once. `change` may read `room`
    /// (for example `room.startYear`) without an exclusive-access conflict.
    private func update(_ id: String, _ change: (inout RoomWire.Player) -> Void) {
        guard let index = room.players.firstIndex(where: { $0.id == id }) else { return }
        var player = room.players[index]
        change(&player)
        room.players[index] = player
    }

    private func broadcast(_ message: RoomWire.Incoming) {
        for continuation in connections.values { continuation.yield(message) }
    }
}

/// Small seeded generator, so the mock rivals play the same way for the same room seed.
struct SplitMix64: Sendable {
    private var state: UInt64

    init(seed: UInt64) { state = seed }

    mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }

    mutating func next(in range: ClosedRange<Int>) -> Int {
        let width = UInt64(range.upperBound - range.lowerBound + 1)
        return range.lowerBound + Int(next() % width)
    }
}
