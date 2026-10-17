import Foundation

/// Backtest of the decision engine (`GET /v1/evaluation`): how often its advice was right in past periods.
struct EvaluationViewState: Equatable, Sendable {
    struct Period: Equatable, Sendable, Identifiable {
        var id: String
        /// "2006 to 2011".
        var rangeText: String
        /// "Advice: Fix 5y. Best in hindsight: Fix 5y."
        var detail: String
        var isHit: Bool
    }

    var phase: LoadPhase
    var method: String
    var hitRate: Double
    var baselineHitRate: Double
    /// "Right in 67% of 24 past periods."
    var hitText: String
    /// "Always fix 2 years: right in 50%."
    var baselineText: String
    var periods: [Period]
    /// "Run on 17 Oct 2026".
    var generatedText: String
}

struct EvaluationActions {
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
