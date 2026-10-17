import Foundation

struct RoomLobbyViewState: Equatable, Sendable {
    struct Player: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var isHost: Bool
        var isMe: Bool
        /// `LLIcon` raw value of the player's face.
        var face: String = "face-teen"
        /// "Ready" or "Joining…".
        var statusText: String = "Ready"
        var isReady: Bool = true
    }

    struct RoomInfo: Equatable, Sendable {
        /// 6 characters, for example "K7Q2ZP".
        var code: String
        var modeLabel: String
        var joinURL: String
        /// QR code PNG from the backend.
        var qrPNG: Data?
        var players: [Player]
        var maxPlayers: Int
        var statusLabel: String
        var startYear: Int
    }

    var phase: LoadPhase
    /// Nil before a room exists: the View shows create and join.
    var room: RoomInfo?
    var joinCode: String
    var canJoin: Bool
    var isHost: Bool
    var canStart: Bool
    /// "Everyone plays the same life" card. Empty without demo data.
    var lifeFace: String = "face-priya"
    /// "Priya, 29, nurse, Leeds. Sep 2021 to Sep 2031. Same events. Your own pace."
    var lifeLine: String = ""
    /// "10 years · 2 rewinds each · real rates to 2026".
    var rulesLine: String = ""
    /// "Players · 4 of 6".
    var playersTitle: String = ""
    /// "Start with 4 players".
    var startTitle: String = "Start"
    var isSampleData: Bool = false
}

struct RoomLobbyActions {
    var onCreate: @MainActor (String) -> Void = { _ in }
    var onJoinCodeChange: @MainActor (String) -> Void = { _ in }
    var onJoin: @MainActor () -> Void = {}
    var onStart: @MainActor () -> Void = {}
    var onLeave: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// Live room: the shared life with the rival strip on top (Play-Live).
struct RoomLiveViewState: Equatable, Sendable {
    struct Stat: Equatable, Sendable, Identifiable {
        var id: String
        /// `LLIcon` raw value.
        var icon: String
        var title: String
        var value: Int
    }

    var name: String
    var face: String
    /// "Age 31 · Room LEEDS4".
    var detail: String
    var bank: Double
    var rivals: RivalStripViewState
    /// "Age · INDEX. Ava: Fixed for 5 years in 2021. Tom: Used a rewind."
    var rivalCaption: String
    /// "2023 · Age 31".
    var storyTitle: String
    var storyLines: [String]
    /// "Lesson: Rate shock".
    var lessonTitle: String
    var stats: [Stat]
    var isSampleData: Bool
}

struct RoomLiveActions {
    var onOpenLesson: @MainActor () -> Void = {}
    var onFinish: @MainActor () -> Void = {}
    var onLeave: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// Live rival strip shown above the Life screen in a room.
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
    }

    var rivals: [Rival]
}

/// End of a room: everyone's result, and where the lives split.
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
        var note: String = ""
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
    /// Earned items: `LLIcon` raw value and text.
    var earned: [RoomDemo.Earned] = []
    var shareText: String = ""
    var isSampleData: Bool = false
}

struct RoomResultActions {
    /// "Rematch".
    var onPlayAgain: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
