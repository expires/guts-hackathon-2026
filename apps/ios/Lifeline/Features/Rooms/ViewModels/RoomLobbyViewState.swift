import Foundation

// View states for Same Life rooms (Play-Lobby, Play-Live, Play-End). Plain values, no networking (ADR 0011).

/// Socket status line on room screens, or the last server error. Nil when the socket is live and all is well.
struct RoomConnectionState: Equatable, Sendable {
    /// `error`: the server refused the last message (`RoomSession.lastError`). It clears by itself.
    enum Kind: Equatable, Sendable { case connecting, reconnecting, offline, error }
    var kind: Kind
    /// "Connecting to the room", "Reconnecting (try 2)", "Connection lost", or the server's error message.
    var text: String
    /// Offline only: shows a "Reconnect" button.
    var canRetry: Bool
    /// Offline or a server error: the banner uses the warning look.
    var isProblem: Bool { kind == .offline || kind == .error }
}

/// Room entry (lobby first, ADR 0059): open a lobby, or join by code or QR.
struct RoomEntryViewState: Equatable, Sendable {
    /// A room you are in. The card reopens it.
    struct ActiveRoom: Equatable, Sendable {
        var code: String
        /// "Lobby · 3 players" or "Playing · Money Quiz".
        var detail: String
    }

    var joinCode: String
    var canJoin: Bool
    var canOpenLobby: Bool
    /// "Opening your lobby" or "Joining K7Q2ZP". Disables the buttons.
    var busyText: String?
    /// Error from the last open or join.
    var errorText: String?
    var activeRoom: ActiveRoom?
    var isSampleData: Bool
}

struct RoomEntryActions {
    var onOpenLobby: @MainActor () -> Void = {}
    var onJoinCodeChange: @MainActor (String) -> Void = { _ in }
    var onJoin: @MainActor () -> Void = {}
    var onScan: @MainActor () -> Void = {}
    var onOpenActiveRoom: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// Room lobby (Play-Lobby): code, QR, share link, players with ready state, host Start.
struct RoomLobbyViewState: Equatable, Sendable {
    struct Player: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var isHost: Bool
        var isMe: Bool
        /// `LLIcon` raw value of the player's face.
        var face: String = "face-teen"
        /// "Ready", "Not ready", "Joining…" or "Away".
        var statusText: String = "Ready"
        var isReady: Bool = true
        var isConnected: Bool = true
    }

    struct RoomInfo: Equatable, Sendable {
        /// 6 characters, for example "K7Q2ZP".
        var code: String
        var modeLabel: String
        var joinURL: String
        /// QR code PNG: from the backend, or drawn from the join link when the backend image does not decode.
        var qrPNG: Data?
        var players: [Player]
        var maxPlayers: Int
        var statusLabel: String
        var startYear: Int
    }

    var phase: LoadPhase
    /// Nil before a room exists.
    var room: RoomInfo?
    var joinCode: String
    var canJoin: Bool
    var isHost: Bool
    var canStart: Bool
    /// "Everyone plays the same life" card. Empty hides it.
    var lifeFace: String = "face-priya"
    /// "Amira, 29, nurse, Leeds. Starts in 2021. Same events. Your own pace."
    var lifeLine: String = ""
    /// "Group · up to 6 players · same events for everyone".
    var rulesLine: String = ""
    /// "Players · 4 of 6".
    var playersTitle: String = ""
    /// "Start with 4 players".
    var startTitle: String = "Start"
    var isSampleData: Bool = false
    /// Socket status. Nil when live.
    var connection: RoomConnectionState? = nil
    /// Shows the "I'm ready" button.
    var canReady: Bool = false
    var isMeReady: Bool = false
    /// "Waiting for Ava to start" for players who are not the host.
    var waitingText: String = ""
    /// Share sheet text with the link.
    var shareText: String = ""
    /// The game the host picked. Nil until then.
    var game: RoomGameCard? = nil
    /// Host only: shows "Pick a game" (or "Change game").
    var canPickGame: Bool = false
}

/// The picked game in the lobby: "Money Quiz · 8 questions · mixed topics".
struct RoomGameCard: Equatable, Sendable {
    var title: String
    var detail: String
    /// `LLIcon` raw value.
    var icon: String
}

struct RoomLobbyActions {
    var onCreate: @MainActor (String) -> Void = { _ in }
    var onJoinCodeChange: @MainActor (String) -> Void = { _ in }
    var onJoin: @MainActor () -> Void = {}
    var onStart: @MainActor () -> Void = {}
    var onLeave: @MainActor () -> Void = {}
    var onReady: @MainActor () -> Void = {}
    var onReconnect: @MainActor () -> Void = {}
    var onPickGame: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// Live room (Play-Live): your life with the rival strip on top.
struct RoomLiveViewState: Equatable, Sendable {
    struct Stat: Equatable, Sendable, Identifiable {
        var id: String
        /// `LLIcon` raw value.
        var icon: String
        var title: String
        var value: Int
    }

    /// The open event of your life. You answer it here or in the Life tab.
    struct Event: Equatable, Sendable {
        struct Choice: Equatable, Sendable, Identifiable {
            var id: String
            var label: String
        }

        var id: String
        var title: String
        var text: String
        var choices: [Choice]
    }

    var name: String
    var face: String
    /// "Age 31 · Room LEEDS4".
    var detail: String
    var bank: Double
    var rivals: RivalStripViewState
    /// "Age · INDEX. Ava: Fixed for 5 years in 2021."
    var rivalCaption: String
    /// "2023 · Age 31".
    var storyTitle: String
    var storyLines: [String]
    /// "Lesson: Rate shock". Empty hides the lesson row.
    var lessonTitle: String
    var stats: [Stat]
    var isSampleData: Bool
    var connection: RoomConnectionState? = nil
    var event: Event? = nil
    /// Shows the Age up button. False hides it (event open, life over, or no life yet).
    var showsAgeUp: Bool = false
    /// Age after the next tap, from the engine life state (`Life.nextAge`). Nil: the button says "Age up"
    /// (Quick Life taps move 1 or 2 years by a server plan the app cannot see).
    var nextAge: Int? = nil
    var isBusy: Bool = false
    /// "Starting your life" while the shared life loads.
    var waitingText: String? = nil
    var canFinish: Bool = true
    /// Shows "Open in Life tab".
    var canOpenLife: Bool = false
    /// Same Life: your room life did not start. A red banner with "Try again". Nil hides it.
    var startError: String? = nil
}

struct RoomLiveActions {
    var onOpenLesson: @MainActor () -> Void = {}
    var onFinish: @MainActor () -> Void = {}
    var onLeave: @MainActor () -> Void = {}
    var onAge: @MainActor () -> Void = {}
    /// Event id, choice id.
    var onChoose: @MainActor (String, String) -> Void = { _, _ in }
    var onOpenLife: @MainActor () -> Void = {}
    var onReconnect: @MainActor () -> Void = {}
    /// "Try again" on the start error banner: starts your room life again.
    var onRetryStart: @MainActor () -> Void = {}
    /// "Not sure? Ask Penny" on the open event. Nil hides the button.
    var onAskPenny: (@MainActor () -> Void)? = nil

    static var noop: Self { .init() }
}

/// Live rival strip: one tile per player.
struct RivalStripViewState: Equatable, Sendable {
    struct Rival: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var age: Int?
        var netWorth: Double?
        var index: Double?
        var isMe: Bool
        var finished: Bool
        var face: String = "face-teen"
        var isConnected: Bool = true
    }

    var rivals: [Rival]
}

/// End of a room (Play-End): ranking by INDEX, net worth, ribbons, and where the lives split.
struct RoomResultViewState: Equatable, Sendable {
    struct Row: Equatable, Sendable, Identifiable {
        var id: String
        var rank: Int
        var name: String
        var index: Double
        var netWorth: Double
        var ribbons: Int
        var isMe: Bool
        var face: String = "face-teen"
        /// Extra text, for example "Still playing". Finished rows show the net worth instead.
        var note: String = ""
        /// False while the player still plays. The row then shows "Still playing".
        var finished: Bool = true
        /// False when the player's ribbons are not known.
        var ribbonsKnown: Bool = true
    }

    struct Split: Equatable, Sendable, Identifiable {
        var id: String
        var year: Int
        var age: Int
        var myChoice: String
        var rivalName: String
        var rivalChoice: String
    }

    var rows: [Row]
    var splits: [Split]
    var winnerName: String
    /// "LEEDS4 · Sep 2021 to Sep 2031".
    var subtitle: String = ""
    /// "Ava · INDEX 131".
    var winnerLine: String = ""
    var winnerNote: String = ""
    /// Winner's net worth. The View formats it, so presentation mode can round it.
    var winnerNetWorth: Double? = nil
    /// Earned items: `LLIcon` raw value and text.
    var earned: [RoomDemo.Earned] = []
    var shareText: String = ""
    var isSampleData: Bool = false
    /// "2 players still playing". Empty when everyone finished.
    var pendingText: String = ""
    /// Shown instead of splits when other lives are not available.
    var splitsNote: String = ""
    /// Penny announces the winner in one line (server line, else a template from the result).
    var pennyLine: String = ""
    /// Quick Life summary card (habit score). Nil for a full Same Life.
    var quickLife: QuickLifeCardState? = nil
    var connection: RoomConnectionState? = nil
}

struct RoomResultActions {
    /// "Rematch".
    var onPlayAgain: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}
    /// "Reconnect" on the connection banner.
    var onReconnect: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// QR scanner screen.
struct RoomScannerViewState: Equatable, Sendable {
    enum Status: Equatable, Sendable {
        case asking
        case scanning
        /// No camera, no permission, or no usage text in Info.plist.
        case unavailable(String)
    }

    var status: Status
    /// "That QR code is not a Lifeline room." after a bad scan.
    var hint: String?
}

struct RoomScannerActions {
    var onScanned: @MainActor (String) -> Void = { _ in }
    var onClose: @MainActor () -> Void = {}
    /// "Type a code instead".
    var onTypeCode: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
