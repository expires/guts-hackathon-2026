import Foundation

/// Habits screen: an overall score and seven factors, each 0 to 100 with a plain English explainer.
struct HabitsViewState: Equatable, Sendable {
    struct Factor: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var explainer: String
        /// 0 to 100. Nil when the backend could not work it out.
        var score: Int?
        /// "70 out of 100", or "Not enough data".
        var scoreText: String
        /// "Going well", "Fine", "Worth a look". Nil without a score.
        var bandText: String?
        /// Why there is no score, for example "Connect Trading212 to see this."
        var reason: String?
    }

    var phase: LoadPhase
    /// 0 to 100. Nil when there is no overall score.
    var overall: Int?
    /// "Last 6 months, up to 30 Sep 2026".
    var windowText: String
    var overallBandText: String?
    var factors: [Factor]
    var isSampleData: Bool
}

struct HabitsActions {
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
