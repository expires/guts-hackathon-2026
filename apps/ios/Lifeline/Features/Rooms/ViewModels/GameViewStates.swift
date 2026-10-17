import Foundation

// View states for the friends games (ADR 0052, 0059): game picker, Money Quiz, Same Decision,
// final ranking, Quick Life card and Circles. Plain values. No £ amount of a real person appears here.

/// One row of the live ranking.
struct RankingRowState: Equatable, Sendable, Identifiable {
    var id: String
    var rank: Int
    var name: String
    var score: Int
    var isMe: Bool
    /// Right in the last round. Nil before the first reveal.
    var lastCorrect: Bool?
    /// `LLIcon` raw value.
    var face: String
}

/// Host's one small sheet: pick a game and its options.
struct GamePickerViewState: Equatable, Sendable {
    struct Option: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var detail: String = ""
        var icon: String = ""
    }

    var games: [Option]
    var selectedGame: String
    /// Money Quiz length, 3 to 15.
    var questions: Int
    var topics: [Option]
    var topic: String
    /// Same Life student paths.
    var paths: [Option]
    var pathID: String?
    var pathsPhase: LoadPhase
    var quick: Bool
    /// Same Decision and Same Life history year.
    var startYear: Int
    var minYear: Int
    var maxYear: Int
    var confirmTitle: String
    var canConfirm: Bool
}

struct GamePickerActions {
    var onSelectGame: @MainActor (String) -> Void = { _ in }
    var onQuestions: @MainActor (Int) -> Void = { _ in }
    var onTopic: @MainActor (String) -> Void = { _ in }
    var onPath: @MainActor (String) -> Void = { _ in }
    var onQuick: @MainActor (Bool) -> Void = { _ in }
    var onYear: @MainActor (Int) -> Void = { _ in }
    var onConfirm: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// Mark on an answer after the reveal.
enum AnswerMark: Equatable, Sendable {
    case none
    /// Your choice, before the reveal.
    case picked
    case correct
    /// Your choice, and it was wrong.
    case wrong
}

/// Money Quiz round.
struct QuizViewState: Equatable, Sendable {
    struct Choice: Equatable, Sendable, Identifiable {
        var id: String
        var text: String
        var mark: AnswerMark
    }

    struct Reveal: Equatable, Sendable {
        /// Penny's one line.
        var explanation: String
        var sourceLabel: String
        var sourceURL: String?
    }

    /// "Question 3 of 8".
    var progressText: String
    var text: String
    var choices: [Choice]
    /// End of the answer window. Nil after the reveal.
    var deadline: Date?
    /// Answer window in seconds (15 by default).
    var duration: Double
    /// True after you answered or after the reveal.
    var isLocked: Bool
    var reveal: Reveal?
    /// Before the reveal: "Answered. Waiting for 2 players." or "Waiting for the next question".
    var statusText: String
    var ranking: [RankingRowState]
    var isSampleData: Bool
    var connection: RoomConnectionState?
}

struct RoundActions {
    /// Choice id.
    var onAnswer: @MainActor (String) -> Void = { _ in }
    var onLeave: @MainActor () -> Void = {}
    var onReconnect: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// Same Decision round.
struct DecisionViewState: Equatable, Sendable {
    struct Option: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var mark: AnswerMark
        /// Names of the players who picked it. Filled at the reveal.
        var pickedBy: [String]
        /// Game money change for this choice. Filled at the reveal. Simulated, never real money.
        var gameMoney: Double?
        var note: String
    }

    /// "2022".
    var yearText: String
    /// What was happening that year.
    var context: String
    var text: String
    var options: [Option]
    var deadline: Date?
    var duration: Double
    var isLocked: Bool
    /// Penny's line at the reveal.
    var pennyLine: String?
    /// Players who did not answer in time, at the reveal.
    var missedText: String
    var statusText: String
    var ranking: [RankingRowState]
    var isSampleData: Bool
    var connection: RoomConnectionState?
}

/// End of a Money Quiz or Same Decision game.
struct GameOverViewState: Equatable, Sendable {
    var gameTitle: String
    /// "Ava wins with 430 points" or "You win with 430 points".
    var winnerLine: String
    var ranking: [RankingRowState]
    var isHost: Bool
    var isSampleData: Bool
}

struct GameOverActions {
    /// Host: back to the lobby to pick another game. Others: leave.
    var onPlayAgain: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// Quick Life summary card (ages 18 to 25). Game money only.
struct QuickLifeCardState: Equatable, Sendable {
    struct Habit: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        /// 0 to 100.
        var value: Int
    }

    var title: String
    var index: Double
    /// Game net worth at the end.
    var gameNetWorth: Double
    var ribbons: Int
    /// 0 to 100 from the engine. Nil when the server has not sent it.
    var habitOverall: Int?
    var habits: [Habit]
}

/// Circles: friends compare habit ratios, never amounts (ADR 0052 privacy rule).
struct CirclesViewState: Equatable, Sendable {
    struct Member: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var isYou: Bool
        /// Rank by improvement against the member's own baseline.
        var rank: Int?
        /// "+6 points" or "-3 points" against their own baseline. Empty when unknown.
        var improvementText: String
        var improvement: Int?
        var overall: Int?
        var habits: [QuickLifeCardState.Habit]
        var face: String
    }

    struct CircleRow: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var code: String
        /// "4 members".
        var detail: String
        var members: [Member]
        var recap: String?
        /// "Week 42".
        var recapWeek: String?
    }

    var phase: LoadPhase
    var circles: [CircleRow]
    var selectedID: String?
    var newName: String
    var canCreate: Bool
    var joinCode: String
    var canJoin: Bool
    var busyText: String?
    var errorText: String?
    var isSampleData: Bool
}

struct CirclesActions {
    var onSelect: @MainActor (String?) -> Void = { _ in }
    var onNameChange: @MainActor (String) -> Void = { _ in }
    var onCreate: @MainActor () -> Void = {}
    var onJoinCodeChange: @MainActor (String) -> Void = { _ in }
    var onJoin: @MainActor () -> Void = {}
    var onLeave: @MainActor (String) -> Void = { _ in }
    var onRetry: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
