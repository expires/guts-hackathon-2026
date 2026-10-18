import Foundation
import Observation

/// Your numbers after an AGE, sent as `progress` and `finish`.
struct RoomProgress: Equatable, Sendable {
    var lifeID: String
    var age: Int
    var year: Int
    var netWorth: Double
    var index: Double

    init(lifeID: String, age: Int, year: Int, netWorth: Double, index: Double) {
        self.lifeID = lifeID
        self.age = age
        self.year = year
        self.netWorth = netWorth
        self.index = index
    }

    init(life: Life) {
        self.init(lifeID: life.id, age: life.age, year: life.year, netWorth: life.finances.netWorth, index: life.index.value)
    }

    func message(_ type: RoomWire.Outgoing._TypePayload, playerID: String?) -> RoomWire.Outgoing {
        .init(_type: type, playerId: playerID, lifeId: lifeID, age: age, year: year, netWorth: netWorth, index: index)
    }
}

/// One Same Life room over the WebSocket: roster, rivals, start, finish, reconnect.
///
/// Flow (contract `x-websocket`): connect, send `join` (with `player_id` after a reconnect), receive `welcome`
/// with your player, then `roster`, `rival`, `started` and `finished`.
/// Reconnect: when the stream ends, or when the app comes back to the foreground, the session opens
/// a new connection and re-joins with `player_id`. Messages from an old connection are dropped.
@MainActor
@Observable
final class RoomSession {
    enum Link: Equatable, Sendable {
        case idle
        case connecting
        case live
        case reconnecting(attempt: Int)
        case offline(String)
    }

    private(set) var room: Room?
    /// Your player id from `welcome`. Sent as `player_id` on every re-join.
    private(set) var myPlayerID: String?
    private(set) var link: Link = .idle
    /// Message of the last `error` from the server. Cleared by the next other message, or after `errorLifetime`.
    private(set) var lastError: String?
    private(set) var hasLeft = false
    /// Number of connections opened. Tests read it.
    private(set) var connectionCount = 0

    // Games (ADR 0059): Money Quiz and Same Decision rounds.
    private(set) var question: PlayWire.Question?
    /// When the current question or decision arrived. The answer window counts from here.
    private(set) var roundStartedAt: Date?
    private(set) var quizReveal: PlayWire.QuizReveal?
    private(set) var prompt: PlayWire.Prompt?
    private(set) var decisionReveal: PlayWire.DecisionReveal?
    private(set) var ranking: [PlayWire.Score] = []
    /// Your choice in the current round.
    private(set) var myAnswer: String?
    /// Penny's one-line winner announcement from the final `finished` message (ADR 0064).
    /// Nil until the server sends it; the results then use a template from the result numbers.
    private(set) var winnerLine: String?
    @ObservationIgnored var now: @MainActor () -> Date = { Date.now }

    @ObservationIgnored let transport: any RoomTransport
    @ObservationIgnored var onStarted: @MainActor (Room) -> Void = { _ in }
    @ObservationIgnored var onFinished: @MainActor (Room) -> Void = { _ in }

    @ObservationIgnored private var name = "You"
    @ObservationIgnored private var connection: (any RoomConnection)?
    @ObservationIgnored private var generation = 0
    @ObservationIgnored private var attempts = 0
    @ObservationIgnored private var listener: Task<Void, Never>?
    @ObservationIgnored private var pinger: Task<Void, Never>?
    @ObservationIgnored private var retry: Task<Void, Never>?
    @ObservationIgnored private var pendingProgress: RoomProgress?
    @ObservationIgnored private var pendingFinish: RoomProgress?
    @ObservationIgnored private var didAnnounceStart = false
    @ObservationIgnored private var didAnnounceFinish = false
    @ObservationIgnored private let retryDelays: [Duration]
    @ObservationIgnored private let pingInterval: Duration?
    @ObservationIgnored private let errorLifetime: Duration?
    @ObservationIgnored private var errorClear: Task<Void, Never>?

    /// - Parameters:
    ///   - retryDelays: wait before each reconnect attempt. After the last one the link is `.offline`.
    ///   - pingInterval: keep-alive `ping` while live. Nil turns it off (tests).
    ///   - errorLifetime: how long `lastError` shows when no other message arrives. Nil keeps it (tests).
    init(
        transport: any RoomTransport,
        retryDelays: [Duration] = [.seconds(1), .seconds(2), .seconds(4), .seconds(8)],
        pingInterval: Duration? = .seconds(20),
        errorLifetime: Duration? = .seconds(5)
    ) {
        self.transport = transport
        self.retryDelays = retryDelays
        self.pingInterval = pingInterval
        self.errorLifetime = errorLifetime
    }

    var me: RoomWire.Player? { room?.players.first { $0.id == myPlayerID } }
    var isHost: Bool { me?.isHost ?? false }

    // MARK: Lifecycle

    /// Starts with a room from `createRoom` or `getRoom`, then connects.
    func open(room: Room, name: String) async {
        self.room = room
        self.name = name
        hasLeft = false
        myPlayerID = nil
        resetGame()
        // Announced after `welcome`, also for a room that already runs (re-open after a restart).
        didAnnounceStart = false
        didAnnounceFinish = false
        attempts = 0
        await connect()
    }

    /// Opens a new connection and sends `join`. Closes the old connection first.
    func connect() async {
        guard let code = room?.code, !hasLeft else { return }
        retry?.cancel()
        generation += 1
        let current = generation
        listener?.cancel()
        pinger?.cancel()
        if let old = connection {
            connection = nil
            await old.close()
        }
        link = myPlayerID == nil && attempts == 0 ? .connecting : .reconnecting(attempt: max(1, attempts))
        do {
            let opened = try await transport.connect(code: code)
            guard current == generation, !hasLeft else {
                await opened.close()
                return
            }
            connection = opened
            connectionCount += 1
            listener = Task { [weak self] in
                for await message in opened.messages {
                    self?.receive(message, generation: current)
                }
                self?.streamEnded(generation: current)
            }
            try await opened.send(.init(_type: .join, playerId: myPlayerID, name: name.isEmpty ? nil : name))
        } catch {
            guard current == generation else { return }
            failed(error)
        }
    }

    /// The app came back to the foreground: the socket may have died during sleep. Re-join with `player_id`.
    func resume() async {
        guard room != nil, !hasLeft else { return }
        attempts = 0
        await connect()
    }

    /// "Reconnect" after the link went offline.
    func reconnect() async {
        attempts = 0
        await connect()
    }

    /// Sends `leave` and closes the socket. The session can then open another room.
    func leave() async {
        guard !hasLeft else { return }
        if let connection, link == .live {
            try? await connection.send(.init(_type: .leave, playerId: myPlayerID))
        }
        hasLeft = true
        generation += 1
        retry?.cancel()
        listener?.cancel()
        pinger?.cancel()
        await connection?.close()
        connection = nil
        link = .idle
        room = nil
        myPlayerID = nil
        pendingProgress = nil
        pendingFinish = nil
        resetGame()
    }

    private func resetGame() {
        question = nil
        quizReveal = nil
        prompt = nil
        decisionReveal = nil
        ranking = []
        myAnswer = nil
        roundStartedAt = nil
        winnerLine = nil
        clearError()
    }

    // MARK: Sending

    /// Host only: the game and its options. The server answers with `game_picked`.
    func pickGame(_ game: RoomGameKind, options: PlayWire.Options) async {
        guard isHost else { return }
        await send(.init(
            _type: .pickGame, playerId: myPlayerID,
            game: RoomWire.Outgoing.GamePayload(rawValue: game.rawValue), options: options
        ))
    }

    /// Answers the current question or decision once.
    func answer(choiceID: String) async {
        guard myAnswer == nil else { return }
        let roundID: String
        if let question, quizReveal == nil {
            roundID = question.id
        } else if let prompt, decisionReveal == nil {
            roundID = prompt.id
        } else {
            return
        }
        myAnswer = choiceID
        await send(.init(_type: .answer, playerId: myPlayerID, questionId: roundID, choiceId: choiceID))
    }

    func ready() async {
        await send(.init(_type: .ready, playerId: myPlayerID))
    }

    /// Host only.
    func start() async {
        guard isHost else { return }
        await send(.init(_type: .start, playerId: myPlayerID))
    }

    /// Sends your numbers after each AGE. Kept and sent again after a reconnect.
    func progress(_ progress: RoomProgress) async {
        pendingProgress = progress
        upsertMe { player in
            player.lifeId = progress.lifeID
            player.age = progress.age
            player.year = progress.year
            player.netWorth = progress.netWorth
            player.index = progress.index
        }
        await send(progress.message(.progress, playerID: myPlayerID))
    }

    /// Ends your run. Kept and sent again after a reconnect.
    func finish(_ progress: RoomProgress) async {
        pendingFinish = progress
        upsertMe { player in
            player.finished = true
            player.netWorth = progress.netWorth
            player.index = progress.index
        }
        await send(progress.message(.finish, playerID: myPlayerID))
    }

    private func send(_ message: RoomWire.Outgoing) async {
        guard let connection, link == .live else { return }
        do {
            try await connection.send(message)
        } catch {
            scheduleReconnect()
        }
    }

    // MARK: Receiving

    /// Applies one server message. Messages from an old connection are dropped.
    func receive(_ message: RoomWire.Incoming, generation: Int) {
        guard generation == self.generation, !hasLeft else { return }
        switch message._type {
        case .welcome:
            if let you = message.you { myPlayerID = you.id }
            if let room = message.room { self.room = room }
            if let you = message.you { upsert(you) }
            becameLive()
            // The UI shows the host as ready (`RoomMapping.isReady`). Send `ready` so the server roster matches.
            if isHost, room?.status == .lobby, me?.ready != true {
                Task { await ready() }
            }
        case .roster:
            if let room = message.room { self.room = room }
            if link != .live, myPlayerID != nil { becameLive() }
        case .rival:
            if let player = message.player { upsert(player) }
        case .started:
            // `started` is a status change. A repeated `started` must not roll back newer rival progress.
            if let room = message.room, self.room?.status != .playing {
                self.room = room
            } else {
                room?.status = .playing
            }
        case .finished:
            if let player = message.player { upsert(player) }
            if let room = message.room { self.room = room }
        case .error:
            showError(message.error?.message ?? L10n.tr("The room sent an error."))
        case .pong:
            break
        case .gamePicked:
            if let room = message.room { self.room = room }
        case .question:
            guard let question = message.question else { break }
            if self.question?.id != question.id { myAnswer = nil; roundStartedAt = now() }
            self.question = question
            quizReveal = nil
            prompt = nil
            decisionReveal = nil
        case .quizReveal:
            guard let reveal = message.quizReveal, reveal.questionId == question?.id else { break }
            quizReveal = reveal
            ranking = reveal.ranking
        case .decision:
            guard let prompt = message.decision else { break }
            if self.prompt?.id != prompt.id { myAnswer = nil; roundStartedAt = now() }
            self.prompt = prompt
            decisionReveal = nil
            question = nil
            quizReveal = nil
        case .decisionReveal:
            guard let reveal = message.decisionReveal, reveal.promptId == prompt?.id else { break }
            decisionReveal = reveal
            ranking = reveal.ranking
        case .ranking:
            if let ranking = message.ranking { self.ranking = ranking }
        case .qlQuestion, .qlFeedback, .qlResults:
            // Quick Life redesign (ADR 0074) is not built in the app yet.
            break
        }
        if message._type != .error, message._type != .pong, lastError != nil { clearError() }
        if message._type == .finished, let ranking = message.ranking { self.ranking = ranking }
        if message._type == .finished, let line = message.winnerLine, !line.isEmpty { winnerLine = line }
        announce()
    }

    private func showError(_ text: String) {
        lastError = text
        errorClear?.cancel()
        guard let lifetime = errorLifetime else { return }
        errorClear = Task { [weak self] in
            try? await Task.sleep(for: lifetime)
            guard !Task.isCancelled else { return }
            self?.clearError()
        }
    }

    private func clearError() {
        errorClear?.cancel()
        errorClear = nil
        lastError = nil
    }

    /// Current connection generation. Tests use it with `receive`.
    var currentGeneration: Int { generation }

    private func becameLive() {
        link = .live
        attempts = 0
        startPinging()
        Task { await flushPending() }
    }

    /// After a re-join, send what the server may have missed.
    private func flushPending() async {
        if let finish = pendingFinish {
            await send(finish.message(.finish, playerID: myPlayerID))
        } else if let progress = pendingProgress {
            await send(progress.message(.progress, playerID: myPlayerID))
        }
    }

    private func announce() {
        guard let room else { return }
        if !didAnnounceStart, room.status != .lobby {
            didAnnounceStart = true
            onStarted(room)
        }
        if !didAnnounceFinish, room.status == .finished {
            didAnnounceFinish = true
            onFinished(room)
        }
    }

    private func streamEnded(generation: Int) {
        guard generation == self.generation, !hasLeft else { return }
        connection = nil
        pinger?.cancel()
        scheduleReconnect()
    }

    private func failed(_ error: any Error) {
        connection = nil
        if let transportError = error as? RoomTransportError {
            link = .offline(transportError.apiError.userMessage)
            return
        }
        let mapped = APIError.map(error)
        if case let .server(status, _, _, _) = mapped, status == 404 || status == 501 {
            link = .offline(mapped.userMessage)
            return
        }
        scheduleReconnect()
    }

    private func scheduleReconnect() {
        guard !hasLeft else { return }
        guard attempts < retryDelays.count else {
            link = .offline(L10n.tr("Connection lost."))
            return
        }
        let delay = retryDelays[attempts]
        attempts += 1
        link = .reconnecting(attempt: attempts)
        retry?.cancel()
        retry = Task { [weak self] in
            try? await Task.sleep(for: delay)
            guard !Task.isCancelled else { return }
            await self?.connect()
        }
    }

    private func startPinging() {
        pinger?.cancel()
        guard let interval = pingInterval else { return }
        pinger = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: interval)
                guard !Task.isCancelled, let self else { return }
                await self.send(.init(_type: .ping, playerId: self.myPlayerID))
            }
        }
    }

    // MARK: Roster helpers

    private func upsert(_ player: RoomWire.Player) {
        guard room != nil else { return }
        if let index = room?.players.firstIndex(where: { $0.id == player.id }) {
            room?.players[index] = player
        } else {
            room?.players.append(player)
        }
    }

    private func upsertMe(_ change: (inout RoomWire.Player) -> Void) {
        guard let id = myPlayerID, var current = room, let index = current.players.firstIndex(where: { $0.id == id }) else { return }
        change(&current.players[index])
        room = current
    }
}
