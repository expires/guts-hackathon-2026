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
    /// "Demo persona · Nurse in Leeds, age 34 · Own home". Empty without a profile.
    var personaLine: String = ""
    /// Best INDEX across your lives, for example "124". "-" without lives.
    var bestIndexText: String = "-"
    var ribbonsText: String = "0"
    /// "3/40".
    var conceptsText: String = "-"
    /// "Demo Bank" or "No bank".
    var bankName: String = ""
    /// "Connected · fake accounts" or "Not connected".
    var bankDetail: String = ""
    /// One row per data source from `GET /v1/sources`.
    var dataRows: [DataRow] = []
    /// Credits sentence plus font licences, from `Resources/Credits.json`.
    var credits: [String] = []

    struct DataRow: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var status: DataStatus
        /// "Saved copy · Bank of England" or "Live" or "Mock data".
        var detail: String
    }
}

/// `Resources/Credits.json`. The You tab shows it.
struct CreditsFile: Decodable, Equatable, Sendable {
    struct FontCredit: Decodable, Equatable, Sendable {
        var name: String
        var authors: String
        var licence: String
    }

    var event: String
    var fonts: [FontCredit]
    var icons: String

    static func load(bundle: Bundle = .main) -> CreditsFile? {
        guard let url = bundle.url(forResource: "Credits", withExtension: "json"),
              let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(CreditsFile.self, from: data)
    }
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
