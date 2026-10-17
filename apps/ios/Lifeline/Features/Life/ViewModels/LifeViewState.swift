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

    /// One year of the story feed, newest first in `years`.
    struct YearGroup: Equatable, Sendable, Identifiable {
        var id: Int { year }
        var year: Int
        var age: Int
        /// "2021 · Age 29".
        var title: String
        var lines: [String]
    }

    /// The open event as a row on the feed. Tapping it opens the full-screen choice.
    struct PendingEvent: Equatable, Sendable {
        var id: String
        var title: String
        /// "Choose before you age up".
        var subtitle: String
        /// Life area for the chip: work, home, money, family or health.
        var area: String
        var areaLabel: String
    }

    var header: Header
    /// "Age 29 · Nurse · Leeds".
    var headerLine: String = ""
    /// Cash ("In the bank").
    var cash: Double = 0
    /// Story feed grouped by year, newest first.
    var years: [YearGroup] = []
    var pendingEvent: PendingEvent? = nil
    /// Life action menus with counts (Job, Assets, People, Money, Activities).
    var menu: LifeMenuViewState = .init(items: [], isEnabled: false)
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
    /// Opens the full-screen choice for the open event.
    var onOpenEvent: @MainActor () -> Void = {}
    /// Opens a Life action menu.
    var onOpenMenu: @MainActor (LifeMenuViewState.Menu) -> Void = { _ in }

    static var noop: Self { .init() }
}
