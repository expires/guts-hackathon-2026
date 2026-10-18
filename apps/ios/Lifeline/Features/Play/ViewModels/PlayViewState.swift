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
        enum Status: Equatable, Sendable {
            case inProgress, won, lost

            var text: String {
                switch self {
                case .inProgress: L10n.tr("In progress")
                case .won: L10n.tr("Done")
                case .lost: L10n.tr("Missed")
                }
            }
        }

        /// "Starts in 2006" for a life challenge. For a "you" challenge: the progress detail from the API.
        var detail: String
        /// True for a challenge scored on your own money (scope "you"). Tapping it shows the Money tab.
        var isYou = false
        /// Progress on a "you" challenge. Nil when there is no progress yet (signed out or no money data).
        var status: Status? = nil
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
    /// Same Life entry for the "Rooms" segment (W9). Nil hides the segment.
    var rooms: RoomEntryViewState? = nil
    /// Circles segment (W9). Nil hides it.
    var circles: CirclesViewState? = nil
    /// The Learn course card (ADR 0068). Nil hides it.
    var learn: LearnEntryState? = nil
    /// PENNY_V3_BUILD F: shows Play solo, Challenges and Collection. The glue sets it from `FeatureFlags`.
    var showsCutFeatures = false
}

struct PlayActions {
    /// Goes to the Life tab. It shows character select when no life is running.
    var onPlay: @MainActor () -> Void = {}
    var onOpenLife: @MainActor (String) -> Void = { _ in }
    var onStartChallenge: @MainActor (String) -> Void = { _ in }
    /// "Play solo": pushes the Life entry.
    var onPlaySolo: @MainActor () -> Void = {}
    /// "Play with friends": opens the room flow.
    var onPlayWithFriends: @MainActor () -> Void = {}
    /// "Join a game": opens the scanner.
    var onJoin: @MainActor () -> Void = {}
    /// Same Life rooms: reopens the room cover.
    var onOpenRooms: @MainActor () -> Void = {}
    var onOpenConcepts: @MainActor () -> Void = {}
    /// "Learn": opens the course path (ADR 0068).
    var onOpenLearn: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}
    /// Create and join buttons for the "Rooms" segment.
    var rooms: RoomEntryActions = .noop
    var circles: CirclesActions = .noop

    static var noop: Self { .init() }
}
