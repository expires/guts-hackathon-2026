import Foundation
import Observation

/// Play with friends (ADR 0052, 0059): lobby first, game second.
///
/// "Play with friends" opens a lobby at once (big QR, short code). Friends join by scan, code or link.
/// The host picks Money Quiz, Same Decision or Same Life on one small sheet, then starts.
/// One instance per `GameSession` (`shared(for:)`), so the Play tab, the deep link and character select
/// share the room. In Same Life your room life is the `GameSession` life.
@MainActor
@Observable
final class RoomFlowViewModel {
    enum Stage: Equatable { case entry, lobby, quiz, decision, live, results, gameOver }

    let game: GameSession
    let session: RoomSession
    let play: any PlayService

    private(set) var paths: [PlayWire.Path] = []
    private(set) var pathsPhase: LoadPhase = .loading(.init(message: "Loading paths"))
    private(set) var joinCode = ""
    private(set) var busyText: String?
    private(set) var errorText: String?
    /// Your account name (`GET /v1/me`). The server uses it; there is no name field (ADR 0059).
    private(set) var myName: String?
    private(set) var myLifeID: String?
    private(set) var rivalLives: [String: Life] = [:]
    /// Summary of your room life, for the Quick Life card (habit score).
    private(set) var mySummary: LifeSummary?
    /// You finished and look at the results while others still play.
    private(set) var showsResultsEarly = false
    /// Host's game sheet.
    var showsGamePicker = false
    private(set) var draft = GameMapping.Draft()
    /// The room cover is on screen. The glue binds to it.
    var isPresented = false
    var showsScanner = false
    /// "Type a code instead" screen.
    var showsCodeEntry = false
    private(set) var scannerHint: String?

    @ObservationIgnored var onOpenLife: @MainActor () -> Void = {}
    @ObservationIgnored private var lastSent: RoomProgress?
    @ObservationIgnored private var qrCache: (key: String, data: Data?)?
    @ObservationIgnored private var requestedLives: Set<String> = []
    @ObservationIgnored private var lastResume: Date?
    /// When the scanner or the code screen last closed. A new cover waits for the close animation.
    @ObservationIgnored private var coverClosedAt: Date?

    init(game: GameSession, session: RoomSession, play: (any PlayService)? = nil) {
        self.game = game
        self.session = session
        self.play = play ?? (session.transport.isMock ? MockPlayService() : ClientPlayService(client: game.client))
        session.onStarted = { [weak self] room in
            Task { await self?.startMyLife(in: room) }
        }
        session.onFinished = { [weak self] _ in
            Task { await self?.refreshResults() }
        }
    }

    convenience init(game: GameSession) {
        self.init(
            game: game,
            session: RoomSession(transport: RoomTransportFactory.make(client: game.client)),
            play: PlayServiceFactory.make(client: game.client)
        )
    }

    // MARK: Shared instance

    private final class WeakBox { weak var model: RoomFlowViewModel? }
    private static var registry: [ObjectIdentifier: WeakBox] = [:]

    /// The room flow for this game. Screens that share a `GameSession` share the room.
    static func shared(for game: GameSession) -> RoomFlowViewModel {
        let key = ObjectIdentifier(game)
        if let model = registry[key]?.model { return model }
        let model = RoomFlowViewModel(game: game)
        let box = WeakBox()
        box.model = model
        registry[key] = box
        return model
    }

    // MARK: Derived

    var gameKind: RoomGameKind? { RoomGameKind(room: session.room?.game) }

    var stage: Stage {
        guard let room = session.room else { return .entry }
        switch (room.status, gameKind) {
        case (.lobby, _): return .lobby
        case (.playing, .quiz): return .quiz
        case (.playing, .sameDecision): return .decision
        case (.playing, _): return myFinished || showsResultsEarly ? .results : .live
        case (.finished, .quiz), (.finished, .sameDecision): return .gameOver
        case (.finished, _): return .results
        }
    }

    var myFinished: Bool { session.me?.finished == true }
    var isSampleData: Bool { session.transport.isMock }

    /// Changes when a player finishes. The glue reloads rival lives on change.
    var resultsKey: String {
        (session.room?.players ?? []).filter { $0.finished == true }.map(\.id).joined(separator: ",")
    }

    /// Changes after each AGE or choice. The glue reports progress on change.
    var lifeKey: String {
        guard let life = game.life else { return "" }
        return "\(life.id)|\(life.year)|\(life.alive)|\(life.history.count)|\(life.finances.netWorth)"
    }

    // MARK: States

    var entryState: RoomEntryViewState {
        let active = session.room.map { room in
            RoomEntryViewState.ActiveRoom(
                code: room.code,
                detail: room.status == .lobby
                    ? "Lobby · \(room.players.count) of \(room.maxPlayers) players"
                    : "Playing · \(gameKind?.title ?? "Same Life")"
            )
        }
        return RoomEntryViewState(
            joinCode: joinCode,
            canJoin: RoomLink.isValid(joinCode) && busyText == nil,
            canOpenLobby: busyText == nil,
            busyText: busyText,
            errorText: errorText,
            activeRoom: active,
            isSampleData: isSampleData
        )
    }

    var lobbyState: RoomLobbyViewState? {
        guard let room = session.room else { return nil }
        return RoomMapping.lobby(room: room, myID: session.myPlayerID, link: session.link, paths: paths, qrPNG: qr(for: room), isSampleData: isSampleData)
    }

    var pickerState: GamePickerViewState {
        GameMapping.picker(draft: draft, paths: paths, pathsPhase: pathsPhase)
    }

    var quizState: QuizViewState? {
        guard let room = session.room else { return nil }
        return GameMapping.quiz(
            question: session.question, reveal: session.quizReveal, myAnswer: session.myAnswer,
            startedAt: session.roundStartedAt, ranking: session.ranking, room: room, myID: session.myPlayerID,
            link: session.link, isSampleData: isSampleData
        )
    }

    var decisionState: DecisionViewState? {
        guard let room = session.room else { return nil }
        return GameMapping.decision(
            prompt: session.prompt, reveal: session.decisionReveal, myAnswer: session.myAnswer,
            startedAt: session.roundStartedAt, ranking: session.ranking, room: room, myID: session.myPlayerID,
            link: session.link, isSampleData: isSampleData
        )
    }

    var gameOverState: GameOverViewState? {
        guard let room = session.room else { return nil }
        return GameMapping.gameOver(room: room, ranking: session.ranking, myID: session.myPlayerID, isSampleData: isSampleData)
    }

    var liveState: RoomLiveViewState? {
        guard let room = session.room else { return nil }
        return RoomMapping.live(room: room, myID: session.myPlayerID, life: myLife, link: session.link, isBusy: game.isBusy, isSampleData: isSampleData)
    }

    var resultState: RoomResultViewState? {
        guard let room = session.room else { return nil }
        var state = RoomMapping.result(room: room, myID: session.myPlayerID, myLife: myLife, rivalLives: rivalLives, link: session.link, isSampleData: isSampleData)
        if let life = myLife, room.options?.quick ?? false {
            let title = paths.first { $0.id == room.options?.pathId }?.title
            state.quickLife = GameMapping.quickLife(life: life, summary: mySummary, pathTitle: title)
        }
        return state
    }

    var scannerHintText: String? { scannerHint }

    private var myLife: Life? { game.life.flatMap { $0.id == myLifeID ? $0 : nil } }

    private func qr(for room: Room) -> Data? {
        let key = room.code + room.qrPngBase64.prefix(64)
        if let qrCache, qrCache.key == key { return qrCache.data }
        let data = RoomQR.png(base64: room.qrPngBase64, joinURL: room.joinUrl)
        qrCache = (key, data)
        return data
    }

    // MARK: Actions

    var entryActions: RoomEntryActions {
        RoomEntryActions(
            onOpenLobby: { [weak self] in Task { await self?.openLobby() } },
            onJoinCodeChange: { [weak self] in self?.joinCode = RoomLink.normalise($0) },
            onJoin: { [weak self] in Task { await self?.join() } },
            onScan: { [weak self] in self?.openScanner() },
            onOpenActiveRoom: { [weak self] in self?.isPresented = true }
        )
    }

    var lobbyActions: RoomLobbyActions {
        RoomLobbyActions(
            onStart: { [weak self] in Task { await self?.session.start() } },
            onLeave: { [weak self] in Task { await self?.leave() } },
            onReady: { [weak self] in Task { await self?.session.ready() } },
            onReconnect: { [weak self] in Task { await self?.session.reconnect() } },
            onPickGame: { [weak self] in self?.openGamePicker() }
        )
    }

    var pickerActions: GamePickerActions {
        GamePickerActions(
            onSelectGame: { [weak self] in if let kind = RoomGameKind(rawValue: $0) { self?.draft.game = kind } },
            onQuestions: { [weak self] in self?.draft.questions = min(15, max(3, $0)) },
            onTopic: { [weak self] in self?.draft.topic = $0 },
            onPath: { [weak self] in self?.draft.pathID = $0 },
            onQuick: { [weak self] in self?.setQuick($0) },
            onYear: { [weak self] in self?.draft.startYear = min(2026, max(1990, $0)) },
            onConfirm: { [weak self] in Task { await self?.confirmGame() } },
            onClose: { [weak self] in self?.showsGamePicker = false }
        )
    }

    /// Money Quiz and Same Decision rounds.
    var roundActions: RoundActions {
        RoundActions(
            onAnswer: { [weak self] choice in Task { await self?.session.answer(choiceID: choice) } },
            onLeave: { [weak self] in Task { await self?.leave() } },
            onReconnect: { [weak self] in Task { await self?.session.reconnect() } }
        )
    }

    var gameOverActions: GameOverActions {
        GameOverActions(
            onPlayAgain: { [weak self] in Task { await self?.rematch() } },
            onClose: { [weak self] in Task { await self?.leave() } }
        )
    }

    var liveActions: RoomLiveActions {
        RoomLiveActions(
            onFinish: { [weak self] in Task { await self?.finishRun() } },
            onLeave: { [weak self] in Task { await self?.leave() } },
            onAge: { [weak self] in Task { await self?.age() } },
            onChoose: { [weak self] event, choice in Task { await self?.choose(eventID: event, choiceID: choice) } },
            onOpenLife: { [weak self] in self?.openLife() },
            onReconnect: { [weak self] in Task { await self?.session.reconnect() } }
        )
    }

    var resultActions: RoomResultActions {
        RoomResultActions(
            onPlayAgain: { [weak self] in Task { await self?.rematch() } },
            onClose: { [weak self] in Task { await self?.leave() } }
        )
    }

    var scannerActions: RoomScannerActions {
        RoomScannerActions(
            onScanned: { [weak self] in self?.scanned($0) },
            onClose: { [weak self] in self?.showsScanner = false },
            onTypeCode: { [weak self] in self?.typeCodeInstead() }
        )
    }

    /// Code screen actions: the code field and Join. The screen stays open on an error.
    var codeEntryActions: RoomEntryActions {
        var actions = entryActions
        actions.onJoin = { [weak self] in Task { await self?.join() } }
        actions.onOpenActiveRoom = { [weak self] in self?.showsCodeEntry = false }
        return actions
    }

    // MARK: Lobby

    /// Student paths for Same Life and Quick Life.
    func loadPaths() async {
        guard paths.isEmpty else { return }
        pathsPhase = .loading(.init(message: "Loading paths"))
        do {
            try await play.loadPaths { [weak self] paths in
                guard let self else { return }
                self.paths = paths
                if draft.pathID == nil { draft.pathID = paths.first { $0.quick }?.id ?? paths.first?.id }
                pathsPhase = .ready
            }
        } catch {
            pathsPhase = .failed(.from(APIError.map(error)))
        }
    }

    /// "Play with friends": opens your lobby at once (`POST /v1/rooms` with an empty body).
    func openLobby() async {
        if session.room != nil {
            isPresented = true
            return
        }
        guard busyText == nil else { return }
        busyText = "Opening your lobby"
        errorText = nil
        isPresented = true
        defer { busyText = nil }
        do {
            let room = try await session.transport.createRoom(.init())
            await open(room)
        } catch {
            errorText = APIError.map(error).userMessage
        }
    }

    /// Joins `joinCode`, or `code` from a deep link or a QR scan.
    /// - Parameter presentCover: false when the caller shows the room itself (`RoomJoinScreen`).
    func join(code: String? = nil, presentCover: Bool = true) async {
        if let code { joinCode = RoomLink.normalise(code) }
        guard RoomLink.isValid(joinCode), busyText == nil else { return }
        if session.room?.code == joinCode {
            isPresented = presentCover
            return
        }
        if session.room != nil { await session.leave() }
        busyText = "Joining room \(joinCode)"
        errorText = nil
        defer { busyText = nil }
        do {
            let room = try await session.transport.getRoom(code: joinCode)
            await open(room, presentCover: presentCover)
        } catch {
            errorText = APIError.map(error).userMessage
        }
    }

    private func open(_ room: Room, presentCover: Bool = true) async {
        resetRun()
        if showsScanner || showsCodeEntry {
            showsScanner = false
            showsCodeEntry = false
            coverClosedAt = .now
        }
        // Two full-screen covers cannot animate at the same time: wait for the scanner or code screen to close.
        if presentCover, let closed = coverClosedAt {
            let left = 0.45 - Date.now.timeIntervalSince(closed)
            if left > 0 { try? await Task.sleep(for: .seconds(left)) }
        }
        isPresented = presentCover
        if myName == nil { myName = await play.myName() }
        await session.open(room: room, name: myName ?? "")
    }

    private func resetRun() {
        myLifeID = nil
        lastSent = nil
        rivalLives = [:]
        requestedLives = []
        mySummary = nil
        showsResultsEarly = false
        showsGamePicker = false
    }

    func openGamePicker() {
        guard session.isHost else { return }
        if let room = session.room, let kind = RoomGameKind(room: room.game) {
            draft.game = kind
            draft.questions = room.options?.questions ?? draft.questions
            draft.topic = room.options?.topic?.rawValue ?? draft.topic
            draft.pathID = room.options?.pathId ?? draft.pathID
            draft.quick = room.options?.quick ?? draft.quick
            draft.startYear = room.options?.startYear ?? draft.startYear
        }
        showsGamePicker = true
        Task { await loadPaths() }
    }

    private func setQuick(_ quick: Bool) {
        draft.quick = quick
        if quick, let id = draft.pathID, !paths.contains(where: { $0.id == id && $0.quick }) {
            draft.pathID = paths.first { $0.quick }?.id
        }
    }

    /// Sends `pick_game` with the options and closes the sheet.
    func confirmGame() async {
        guard pickerState.canConfirm else { return }
        showsGamePicker = false
        await session.pickGame(draft.game, options: draft.options)
    }

    // MARK: Join helpers

    func openScanner() {
        scannerHint = nil
        showsScanner = true
    }

    /// Scanner: "Type a code instead". Closes the scanner, then opens the code screen.
    func typeCodeInstead() {
        showsScanner = false
        coverClosedAt = .now
        Task {
            try? await Task.sleep(for: .milliseconds(450))
            showsCodeEntry = true
        }
    }

    func scanned(_ text: String) {
        guard let code = RoomLink.code(fromScanned: text) else {
            scannerHint = "That QR code is not a \(Brand.productName) room."
            return
        }
        showsScanner = false
        coverClosedAt = .now
        Task { await join(code: code) }
    }

    // MARK: Same Life

    /// Starts the shared life: the room's path, year and seed (Quick Life when `quick`). Re-uses a life already in this room.
    func startMyLife(in room: Room) async {
        guard RoomGameKind(room: room.game) == .sameLife || room.game == nil else { return }
        if let life = game.life, life.roomCode == room.code || life.id == myLifeID {
            myLifeID = life.id
        } else {
            let request = CreateLifeRequest(
                mode: .random, startYear: room.gameStartYear, presetId: room.presetId, seed: room.seed,
                roomCode: room.code, pathId: room.options?.pathId, quick: room.options?.quick
            )
            guard await game.startLife(request), let life = game.life else {
                errorText = game.errorMessage ?? "Your life did not start."
                return
            }
            myLifeID = life.id
        }
        await lifeChanged()
    }

    /// Sends `progress` after each AGE or choice, and `finish` when the life ends.
    func lifeChanged() async {
        guard let life = game.life, life.id == myLifeID, session.room?.status == .playing, !myFinished else { return }
        if !life.alive || life.reachedPresent == true {
            await finishRun()
            return
        }
        let progress = RoomProgress(life: life)
        guard progress != lastSent else { return }
        lastSent = progress
        await session.progress(progress)
    }

    func age() async {
        await game.age()
        await lifeChanged()
    }

    func choose(eventID: String, choiceID: String) async {
        await game.choose(choiceID: choiceID, eventID: eventID)
        await lifeChanged()
    }

    func finishRun() async {
        guard let life = game.life, life.id == myLifeID, !myFinished else {
            showsResultsEarly = true
            return
        }
        await session.finish(RoomProgress(life: life))
        showsResultsEarly = true
        await refreshResults()
    }

    /// Another tab was chosen (for example "Ask Penny" from a life event): hide every room cover.
    /// The room, its socket and your life stay; "Back to room" and Play solo reopen them.
    func hideCovers() {
        isPresented = false
        showsScanner = false
        showsCodeEntry = false
        showsGamePicker = false
    }

    /// Hides the room cover and shows your life in Play solo. The socket stays open.
    func openLife() {
        isPresented = false
        onOpenLife()
    }

    // MARK: Results

    /// Loads finished rivals' lives for ribbons and split points (`GET /v1/lives/{id}`; room members get 200,
    /// ADR 0044), and your own summary for the Quick Life habit score. A 404 or an error keeps the row.
    func refreshResults() async {
        guard let room = session.room else { return }
        if mySummary == nil, myFinished, let id = myLifeID {
            mySummary = try? await game.client.summary(lifeID: id)
        }
        for player in room.players where player.id != session.myPlayerID && player.finished == true {
            guard let id = player.lifeId, rivalLives[id] == nil, !requestedLives.contains(id) else { continue }
            requestedLives.insert(id)
            if let life = try? await session.transport.life(id: id) { rivalLives[id] = life }
            requestedLives.remove(id)
        }
    }

    /// Host: a new lobby for the same group. Others leave.
    func rematch() async {
        let wasHost = session.isHost
        await session.leave()
        resetRun()
        if wasHost {
            await openLobby()
        } else {
            isPresented = false
        }
    }

    func leave() async {
        await session.leave()
        resetRun()
        isPresented = false
    }

    /// The app came back to the foreground. Several screens may call this; one resume per second.
    func appBecameActive(now: Date = .now) async {
        if let lastResume, now.timeIntervalSince(lastResume) < 1 { return }
        lastResume = now
        await session.resume()
    }
}
