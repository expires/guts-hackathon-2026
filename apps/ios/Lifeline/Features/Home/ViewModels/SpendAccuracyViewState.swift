import Foundation

/// How good the spend model is: the walk-forward backtest (`/v1/finance/prediction/evaluation`, ADR 0017).
struct SpendAccuracyViewState: Equatable, Sendable {
    struct Day: Equatable, Sendable, Identifiable {
        var id: String
        var dateText: String
        var predicted: Double
        var low: Double
        var high: Double
        var actual: Double
        var baseline: Double
        var isInRange: Bool
    }

    var phase: LoadPhase
    /// "Walk-forward: train on days before each test day, predict the next day".
    var method: String
    /// "Tested on 90 days".
    var daysText: String
    var mae: Double
    var baselineMAE: Double
    /// "The model is off by £11.30 on a typical day."
    var modelText: String
    /// "Average spend for that weekday is off by £14.90."
    var baselineText: String
    /// "81% of days fell inside the range."
    var coverageText: String
    var days: [Day]
    var isSampleData: Bool
}

struct SpendAccuracyActions {
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
