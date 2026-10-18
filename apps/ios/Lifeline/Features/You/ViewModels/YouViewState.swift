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
    /// "Not connected. The Money tab shows a sample statement."
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
    /// "3/40". Kept for the cut concepts collection.
    var conceptsText: String = "-"
    /// "Lessons 3/48" tile (PENNY_V3_BUILD E5): "3/48", or "-" before the Learn path loads.
    var lessonsText: String = "-"
    /// One honesty line under "Your money and data" (PENNY_V3_BUILD B4).
    var honestyText: String = ""
    /// "Safety buffer" setting (B2): the stored buffer %. Nil until the forecast loads or without one.
    var buffer: BufferSetting? = nil
    /// PENNY_V3_BUILD F: shows the cut rows (plan, advice check, spend guess check).
    var showsCutFeatures = false
    /// "Demo Bank" or "No bank".
    var bankName: String = ""
    /// "Connected · fake accounts" or "Not connected".
    var bankDetail: String = ""
    /// One row per data source from `GET /v1/sources`.
    var dataRows: [DataRow] = []
    /// Credits sentence plus font licences, from `Resources/Credits.json`.
    var credits: [String] = []
    /// "Connect your money" row: "Connected: your bank", "Statement imported", "Not connected".
    /// Calm text on an error ("Couldn't load. Pull to refresh."). Nil while loading.
    var connectMoneyText: String? = nil
    /// Presentation mode switch (stored in `@AppStorage("llPresentationMode")` by the glue).
    var isPresentationMode = false
    /// Always nil since PENNY_V3_BUILD B4 (no "Mock data" or "Sample data" tags). Kept for older tests.
    var dataBadgeText: String? = nil
    /// "How good is the advice?" shows only when the backtest has at least one case (n > 0).
    var showsEvaluation = false
    /// Habit score card (ADR 0066): ratios only, never amounts. Nil until loaded or without data.
    var habits: HabitCard? = nil
    /// "Version" row: checkpoint, build time and features from Info.plist.
    var buildInfo = YouBuildInfo(appName: Brand.productName, version: "1.0", checkpoint: nil, builtText: nil, features: [])

    /// Safety buffer chips: 0, 5, 10, 15 or 20%.
    struct BufferSetting: Equatable, Sendable {
        var selected: Int
        var options: [Int] = [0, 5, 10, 15, 20]
        var isSaving = false
        /// "Couldn't save your buffer. Try again." Nil when fine.
        var errorText: String? = nil
    }

    struct DataRow: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var status: DataStatus
        /// "Live", "Saved copy", "Checked figures" or "Not live now". Never "Mock data" (B4).
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

/// Habit score (ADR 0066): an overall score and six ratios, each 0 to 100. No amounts.
struct HabitCard: Equatable, Sendable {
    struct Row: Equatable, Sendable, Identifiable {
        /// "savings_rate".
        var id: String
        /// "Savings rate".
        var name: String
        var value: Int
    }

    var overall: Int?
    var rows: [Row]
}

struct YouActions {
    /// "Connect your money" (router `openConnectMoney()`).
    var onConnectMoney: @MainActor () -> Void = {}
    /// "Your profile": the stats page.
    var onOpenProfile: @MainActor () -> Void = {}
    /// Profile row: opens Account (sign out, reset, delete).
    var onOpenAccount: @MainActor () -> Void = {}
    /// "Ask Penny" row.
    var onAskPenny: @MainActor () -> Void = {}
    /// Judge mode (DIRECTION_V2 section 4): a fresh demo account, then onboarding.
    var onNewPlayer: @MainActor () -> Void = {}
    /// Judge mode: clears demo accounts and lobby state, then onboarding.
    var onResetDemo: @MainActor () -> Void = {}
    /// "How Penny uses AI" (ADR 0043).
    var onOpenAIDisclosure: @MainActor () -> Void = {}
    /// Presentation mode switch.
    var onSetPresentationMode: @MainActor (Bool) -> Void = { _ in }
    /// Pull to refresh.
    var onRefresh: @MainActor () async -> Void = {}
    /// Bank connection (W7).
    var onConnectBank: @MainActor () -> Void = {}
    var onOpenPlan: @MainActor () -> Void = {}
    var onOpenSources: @MainActor () -> Void = {}
    /// Backtest of the decision engine (`/v1/evaluation`).
    var onOpenEvaluation: @MainActor () -> Void = {}
    /// Spend model accuracy (`/v1/finance/prediction/evaluation`). Cut (PENNY_V3_BUILD F1).
    var onOpenSpendAccuracy: @MainActor () -> Void = {}
    /// "Lessons X/48": opens the Learn path (PENNY_V3_BUILD E5).
    var onOpenLearn: @MainActor () -> Void = {}
    /// "Safety buffer": stores the buffer % (PUT /v1/forecast/settings).
    var onSetBuffer: @MainActor (Int) -> Void = { _ in }
    /// "Change language" (ADR 0063).
    var onChangeLanguage: @MainActor () -> Void = {}
    var onOpenDebug: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
