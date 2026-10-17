import Foundation

struct RoomLobbyViewState: Equatable, Sendable {
    struct Player: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var isHost: Bool
        var isMe: Bool
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
}

struct RoomLobbyActions {
    var onCreate: @MainActor (String) -> Void = { _ in }
    var onJoinCodeChange: @MainActor (String) -> Void = { _ in }
    var onJoin: @MainActor () -> Void = {}
    var onStart: @MainActor () -> Void = {}
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
}

struct RoomResultActions {
    var onPlayAgain: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
