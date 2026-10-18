import Foundation

/// Fixtures for the W9 room screens. Built with `RoomMapping` from contract types, so previews,
/// the Playground and tests use the same mapping as the app. All data is mock data.
@MainActor
enum RoomFlowFixtures {
    static let myID = "p1"

    /// 4-player room: you (host), Ava, Tom and Jas. Jas is not ready yet.
    static let lobbyRoom: Room = ContractExamples.decode(#"""
    {
      "code": "4242", "mode": "group", "seed": 777042, "preset_id": "nurse-leeds", "start_year": 2021,
      "max_players": 6,
      "players": [
        {"id": "p1", "name": "Ash", "is_host": true, "ready": true, "connected": true, "finished": false},
        {"id": "p2", "name": "Ava", "is_host": false, "ready": true, "connected": true, "finished": false},
        {"id": "p3", "name": "Tom", "is_host": false, "ready": true, "connected": true, "finished": false},
        {"id": "p4", "name": "Jas", "is_host": false, "ready": false, "connected": true, "finished": false}
      ],
      "join_url": "lifeline://join/4242", "qr_png_base64": "iVBORw0KGgo=", "status": "lobby"
    }
    """#)

    static var playingRoom: Room {
        var room = lobbyRoom
        room.status = .playing
        let numbers: [(age: Int, year: Int, worth: Double, index: Double, finished: Bool)] = [
            (life.age, life.year, life.finances.netWorth, life.index.value, false),
            (33, 2025, 52_800, 108, false),
            (30, 2022, 38_900, 99, false),
            (32, 2024, 35_100, 91, false),
        ]
        for offset in room.players.indices {
            let value = numbers[offset]
            room.players[offset].ready = true
            room.players[offset].lifeId = offset == 0 ? life.id : MockRoomServer.lifeID(rival: room.players[offset].id)
            room.players[offset].age = value.age
            room.players[offset].year = value.year
            room.players[offset].netWorth = value.worth
            room.players[offset].index = value.index
            room.players[offset].finished = value.finished
        }
        room.players[3].connected = false
        return room
    }

    static var finishedRoom: Room {
        var room = playingRoom
        room.status = .finished
        let finals: [(Double, Double)] = [(88_400, 104), (112_600, 131), (97_300, 112), (71_900, 91)]
        for offset in room.players.indices {
            room.players[offset].finished = true
            room.players[offset].connected = true
            room.players[offset].netWorth = finals[offset].0
            room.players[offset].index = finals[offset].1
            room.players[offset].year = 2031
        }
        return room
    }

    /// Your life in the room: the contract example life with two decisions and one ribbon.
    static var life: Life {
        var life = ContractExamples.lifeReadyToAge
        life.id = "lf_room01"
        life.roomCode = "4242"
        life.history += [
            YearLog(year: 2021, age: 29, text: "Fixed for 2 years at 1.28%.", eventId: "ev-2021-1", choiceId: "fix2", netWorth: 9_000, autopilotNetWorth: 9_000, index: 100),
            YearLog(year: 2023, age: 31, text: "Cut the takeaway budget by £60 a month.", eventId: "ev-2023-1", choiceId: "cut", netWorth: 14_200, autopilotNetWorth: 13_100, index: 104),
        ]
        life.ribbons = [.init(id: "rate-shock", title: "Rate shock survivor", emoji: "🎗️", reason: "Kept paying after the fix ended")]
        return life
    }

    static var lifeWithEvent: Life {
        var life = life
        life.pendingEvents = [ContractExamples.event]
        return life
    }

    /// Rival lives for split points. Ava fixed for 5 years in 2021; Tom made the same choices.
    static var rivalLives: [String: Life] {
        var ava = life
        ava.id = MockRoomServer.lifeID(rival: "p2")
        ava.history = ava.history.map { entry in
            guard entry.eventId == "ev-2021-1" else { return entry }
            var copy = entry
            copy.choiceId = "fix5"
            copy.text = "Fixed for 5 years at 1.28%."
            return copy
        }
        ava.ribbons = [life.ribbons[0], .init(id: "saver", title: "Saver", emoji: "🐷", reason: "Saved 10% of pay")]
        var tom = life
        tom.id = MockRoomServer.lifeID(rival: "p3")
        return [ava.id: ava, tom.id: tom]
    }

    static var presets: [CharacterSpec] { ContractExamples.characters.presets }

    // MARK: States

    static func entry(joinCode: String = "", busy: String? = nil, error: String? = nil, active: RoomEntryViewState.ActiveRoom? = nil) -> RoomEntryViewState {
        RoomEntryViewState(
            joinCode: joinCode,
            canJoin: RoomLink.isValid(joinCode) && busy == nil,
            canOpenLobby: busy == nil,
            busyText: busy,
            errorText: error,
            activeRoom: active,
            isSampleData: true
        )
    }

    static var entryReady: RoomEntryViewState { entry() }
    static var entryOpening: RoomEntryViewState { entry(busy: "Opening your lobby") }
    static var entryJoining: RoomEntryViewState { entry(joinCode: "1234", busy: "Joining room 1234") }
    static var entryError: RoomEntryViewState { entry(joinCode: "ZZZZZZ", error: "That room does not exist.") }
    static var entryActive: RoomEntryViewState { entry(active: .init(code: "4242", detail: "Playing · Money Quiz")) }

    /// The lobby with a picked Money Quiz.
    static var quizRoom: Room {
        var room = lobbyRoom
        room.game = .quiz
        room.options = .init(questions: 6, topic: .mixed)
        return room
    }

    /// "Play with friends" lobby (no preset) with Quick Life picked: everyone plays Jordan. Jas never sent "ready".
    static var quickLifeRoom: Room {
        var room = lobbyRoom
        room.presetId = nil
        room.game = .sameLife
        room.options = .init(pathId: "apprentice", quick: true, quickStudentId: "qs-jordan")
        return room
    }

    static func lobby(room: Room = quizRoom, myID: String = myID, link: RoomSession.Link = .live) -> RoomLobbyViewState {
        RoomMapping.lobby(
            room: room, myID: myID, link: link, paths: MockPlayData.paths, students: MockPlayData.quickStudents,
            qrPNG: RoomQR.generate(room.joinUrl), isSampleData: true
        )
    }

    static var lobbyHost: RoomLobbyViewState { lobby() }
    static var lobbyHostNoGame: RoomLobbyViewState { lobby(room: lobbyRoom) }
    static var lobbyGuest: RoomLobbyViewState { lobby(myID: "p4") }
    static var lobbyReconnecting: RoomLobbyViewState { lobby(link: .reconnecting(attempt: 2)) }
    static var lobbyQuickHost: RoomLobbyViewState { lobby(room: quickLifeRoom) }
    static var lobbyQuickGuest: RoomLobbyViewState { lobby(room: quickLifeRoom, myID: "p4") }

    static func picker(_ game: RoomGameKind, quick: Bool = false, step: GamePickerViewState.Step = .games) -> GamePickerViewState {
        var draft = GameMapping.Draft()
        draft.game = game
        draft.quick = quick
        draft.pathID = "uni"
        return GameMapping.picker(
            draft: draft, paths: MockPlayData.paths, students: MockPlayData.quickStudents, pathsPhase: .ready,
            step: step, showsCutFeatures: game == .sameDecision || (game == .sameLife && !quick)
        )
    }

    /// The game list as the host first sees it: Quick Life first, then Money Quiz.
    static var pickerGames: GamePickerViewState { picker(.sameLife, quick: true) }
    /// Quick Life: the 5 premade students.
    static var pickerStudents: GamePickerViewState { picker(.sameLife, quick: true, step: .students) }
    static var pickerQuiz: GamePickerViewState { picker(.quiz) }
    /// Cut games, shown only with `FeatureFlags.showsCutFeatures`.
    static var pickerDecision: GamePickerViewState { picker(.sameDecision) }
    static var pickerSameLife: GamePickerViewState { picker(.sameLife) }

    static var quizPlaying: Room {
        var room = quizRoom
        room.status = .playing
        return room
    }

    static let quizScores: [PlayWire.Score] = [
        .init(playerId: "p2", name: "Ava", score: 230, rank: 1, lastCorrect: true),
        .init(playerId: "p1", name: "Ash", score: 210, rank: 2, lastCorrect: true),
        .init(playerId: "p3", name: "Tom", score: 100, rank: 3, lastCorrect: false),
        .init(playerId: "p4", name: "Jas", score: 0, rank: 4, lastCorrect: false),
    ]

    static var quizQuestion: QuizViewState {
        GameMapping.quiz(
            question: MockPlayData.questions[2], reveal: nil, myAnswer: nil, startedAt: Date(timeIntervalSinceNow: -4),
            ranking: quizScores, room: quizPlaying, myID: myID, link: .live, isSampleData: true
        )
    }

    static var quizReveal: QuizViewState {
        let question = MockPlayData.questions[2]
        let reveal = PlayWire.QuizReveal(
            questionId: question.id, correctChoiceId: "b", explanation: MockPlayData.answers[question.id]?.line ?? "",
            sourceLabel: question.sourceLabel, sourceUrl: question.sourceUrl, ranking: quizScores
        )
        return GameMapping.quiz(
            question: question, reveal: reveal, myAnswer: "a", startedAt: nil,
            ranking: quizScores, room: quizPlaying, myID: myID, link: .live, isSampleData: true
        )
    }

    static var decisionPlaying: Room {
        var room = quizPlaying
        room.game = .sameDecision
        return room
    }

    static var decisionOpen: DecisionViewState {
        GameMapping.decision(
            prompt: MockPlayData.prompts[0], reveal: nil, myAnswer: "lisa", startedAt: Date(timeIntervalSinceNow: -6),
            ranking: [], room: decisionPlaying, myID: myID, link: .live, isSampleData: true
        )
    }

    static var decisionReveal: DecisionViewState {
        let prompt = MockPlayData.prompts[0]
        let result = MockPlayData.outcomes[prompt.id]!
        let reveal = PlayWire.DecisionReveal(
            promptId: prompt.id,
            choices: [
                .init(playerId: "p1", name: "Ash", optionId: "lisa"),
                .init(playerId: "p2", name: "Ava", optionId: "lisa"),
                .init(playerId: "p3", name: "Tom", optionId: "festival"),
                .init(playerId: "p4", name: "Jas", optionId: nil),
            ],
            outcomes: result.outcomes, pennyLine: result.line, ranking: quizScores
        )
        return GameMapping.decision(
            prompt: prompt, reveal: reveal, myAnswer: "lisa", startedAt: nil,
            ranking: quizScores, room: decisionPlaying, myID: myID, link: .live, isSampleData: true
        )
    }

    static var gameOver: GameOverViewState {
        var room = quizPlaying
        room.status = .finished
        return GameMapping.gameOver(room: room, ranking: quizScores, myID: myID, isSampleData: true)
    }

    static var circles: CirclesViewState {
        GameMapping.circles(MockPlayData.circles, phase: .ready, selectedID: nil, newName: "", joinCode: "", busyText: nil, errorText: nil, isSampleData: true)
    }

    static var circleDetail: CirclesViewState {
        GameMapping.circles(MockPlayData.circles, phase: .ready, selectedID: "c1", newName: "", joinCode: "", busyText: nil, errorText: nil, isSampleData: true)
    }

    static var circlesEmpty: CirclesViewState {
        GameMapping.circles([], phase: .ready, selectedID: nil, newName: "Flat 4B", joinCode: "", busyText: nil, errorText: nil, isSampleData: true)
    }

    static func live(life: Life? = RoomFlowFixtures.life, link: RoomSession.Link = .live, room: Room? = nil) -> RoomLiveViewState {
        RoomMapping.live(room: room ?? playingRoom, myID: myID, life: life, link: link, isBusy: false, isSampleData: true)
    }

    static var liveAge: RoomLiveViewState { live() }
    static var liveEvent: RoomLiveViewState { live(life: lifeWithEvent) }
    static var liveStarting: RoomLiveViewState { live(life: nil, link: .connecting) }
    static var liveOffline: RoomLiveViewState { live(link: .offline("Connection lost.")) }

    static var resultFinal: RoomResultViewState {
        RoomMapping.result(room: finishedRoom, myID: myID, myLife: life, rivalLives: rivalLives, link: .live, isSampleData: true)
    }

    static var resultQuickLife: RoomResultViewState {
        var state = resultFinal
        var summary = ContractExamples.summary
        summary.habitScore = MockPlayData.habits([24, 40, 63, 35, 12, 20], overall: 61)
        state.quickLife = GameMapping.quickLife(life: life, summary: summary, pathTitle: "University")
        return state
    }

    static var resultPending: RoomResultViewState {
        var room = playingRoom
        room.players[0].finished = true
        room.players[1].finished = true
        return RoomMapping.result(room: room, myID: myID, myLife: life, rivalLives: [:], link: .live, isSampleData: true)
    }

    static let scannerScanning = RoomScannerViewState(status: .scanning)
    static let scannerBadCode = RoomScannerViewState(status: .scanning, hint: "That QR code is not a \(Brand.productName) room.")
    static let scannerUnavailable = RoomScannerViewState(status: .unavailable("This device has no camera. Type the room code instead."))
}
