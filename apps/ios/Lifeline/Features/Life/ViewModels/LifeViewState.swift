import Foundation

struct LifeViewState: Equatable, Sendable {
    struct Header: Equatable, Sendable {
        var emoji: String
        var name: String
        var age: Int
        var year: Int
        var jobTitle: String
        var town: String
        var isAlive: Bool
        var causeOfDeath: String?
    }

    var header: Header
    var netWorth: Double
    /// 100 = same as the autopilot life.
    var index: Double
    var stats: [StatState]
    var outcome: OutcomeState?
    var canAge: Bool
    var isAging: Bool
    /// Plain English reason when AGE is blocked, or "Live one more year."
    var ageHint: String
    /// Changes after each AGE. Drives the age-up haptic.
    var ageCount: Int
    /// Newest last. The View shows newest first.
    var history: [HistoryItemState]
    var usesSampleData: Bool
    var conceptsUnlocked: Int
    /// For example "1 free rewind left".
    var rewindText: String
    var canRewind: Bool
    var activitiesCount: Int
    /// Dead: show "See your life summary".
    var showsSummary: Bool
    /// Play yourself reached today: show "Your real-life decision".
    var showsDecision: Bool
}

struct LifeActions {
    var onAge: @MainActor () -> Void = {}
    var onDismissOutcome: @MainActor () -> Void = {}
    var onOpenActivities: @MainActor () -> Void = {}
    var onOpenRewind: @MainActor () -> Void = {}
    var onOpenConcepts: @MainActor () -> Void = {}
    var onOpenSources: @MainActor () -> Void = {}
    var onOpenSummary: @MainActor () -> Void = {}
    var onOpenDecision: @MainActor () -> Void = {}
    var onNewLife: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
