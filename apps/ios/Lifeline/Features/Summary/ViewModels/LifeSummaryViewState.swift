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
        /// Index change in the year of the moment, for example "+3" or "-4". Nil without timeline data.
        var indexDelta: String? = nil
        var isDown: Bool = false
    }

    struct TimelinePoint: Equatable, Sendable, Identifiable {
        var year: Int
        var netWorth: Double
        var autopilotNetWorth: Double
        var age: Int = 0
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
    /// "Amira's life".
    var title: String = ""
    /// "1982 to 2061 · lived to 79" or "Born 1982 · age 40".
    var lifespanText: String = ""
    /// "119".
    var indexText: String = ""
    /// "19 points ahead of your autopilot twin."
    var indexSentence: String = ""
    /// Text for the share sheet. Every number comes from the summary.
    var shareText: String = ""
    var isSampleData: Bool = false
}

struct LifeSummaryActions {
    var onNewLife: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
