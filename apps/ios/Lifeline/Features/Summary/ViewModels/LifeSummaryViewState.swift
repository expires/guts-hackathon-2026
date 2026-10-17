import Foundation

struct LifeSummaryViewState: Equatable, Sendable {
    struct Ribbon: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String
        var title: String
        var reason: String
    }

    struct Moment: Equatable, Sendable, Identifiable {
        var id: String
        var year: Int
        var age: Int
        var emoji: String
        var text: String
    }

    struct TimelinePoint: Equatable, Sendable, Identifiable {
        var year: Int
        var netWorth: Double
        var autopilotNetWorth: Double
        var id: Int { year }
    }

    var phase: LoadPhase
    var emoji: String
    var name: String
    var born: Int
    /// Nil while the life is still running.
    var died: Int?
    var age: Int
    var causeOfDeath: String?
    var finalIndex: Double
    var netWorth: Double
    var autopilotNetWorth: Double
    var ribbons: [Ribbon]
    var keyMoments: [Moment]
    var conceptsUnlocked: Int
    var timeline: [TimelinePoint]
}

struct LifeSummaryActions {
    var onNewLife: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
