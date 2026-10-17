import Foundation

/// Play tab (ADR 0016): your lives, Same Life rooms, challenges, ribbons and concepts.
struct PlayViewState: Equatable, Sendable {
    struct LifeRow: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String
        var name: String
        /// "Age 26 in 2008" or "Died at 81 in 2063".
        var detail: String
        var isAlive: Bool
        var index: Double
        var netWorth: Double
        var ribbons: Int
        /// True for the life open in the Life tab.
        var isCurrent: Bool
    }

    struct ChallengeRow: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String
        var title: String
        var description: String
        /// "Starts in 2006".
        var detail: String
    }

    var phase: LoadPhase
    var lives: [LifeRow]
    var challenges: [ChallengeRow]
    var ribbonsTotal: Int
    /// "4 ribbons across 3 lives".
    var ribbonsText: String
    var conceptsUnlocked: Int
    var conceptsTotal: Int
    /// "2 of 12 concepts collected".
    var conceptsText: String
    /// Text for the "continue" row, for example "Continue as Amira, age 26". Nil without a running life.
    var continueText: String?
    var isSampleData: Bool
    /// Disables start buttons while a life is starting.
    var isBusy: Bool
}

struct PlayActions {
    /// Goes to the Life tab. It shows character select when no life is running.
    var onPlay: @MainActor () -> Void = {}
    var onOpenLife: @MainActor (String) -> Void = { _ in }
    var onStartChallenge: @MainActor (String) -> Void = { _ in }
    /// Same Life rooms (W7).
    var onOpenRooms: @MainActor () -> Void = {}
    var onOpenConcepts: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
