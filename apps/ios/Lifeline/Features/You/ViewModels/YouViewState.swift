import Foundation

/// You tab (ADR 0016): profile from your money data, bank connection, plan, data and settings.
struct YouViewState: Equatable, Sendable {
    struct Profile: Equatable, Sendable {
        var emoji: String
        var name: String
        /// "Analyst in Leeds, age 34".
        var detail: String
        var annualIncome: Double
        var savings: Double
        /// "Renting, £850 a month".
        var housingText: String
    }

    var profilePhase: LoadPhase
    var profile: Profile?
    /// Real-number sentences, for example "You spend £47 a month on 6 subscriptions."
    var personalFacts: [String]
    /// "Not connected. The Money tab shows sample data."
    var bankText: String
    /// "live" or "mock".
    var clientText: String
    /// "1.0 (1)".
    var versionText: String
    /// Debug builds only.
    var showsDebugMenu: Bool
    var isSampleData: Bool
}

struct YouActions {
    /// Bank connection (W7).
    var onConnectBank: @MainActor () -> Void = {}
    var onOpenPlan: @MainActor () -> Void = {}
    var onOpenSources: @MainActor () -> Void = {}
    /// Backtest of the decision engine (`/v1/evaluation`).
    var onOpenEvaluation: @MainActor () -> Void = {}
    /// Spend model accuracy (`/v1/finance/prediction/evaluation`).
    var onOpenSpendAccuracy: @MainActor () -> Void = {}
    var onOpenStore: @MainActor () -> Void = {}
    var onOpenDebug: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
