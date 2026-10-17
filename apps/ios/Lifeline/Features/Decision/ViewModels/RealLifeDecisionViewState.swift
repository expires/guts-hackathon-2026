import Foundation

/// Why the Real-life Decision screen is open. Changes the title and the extra actions.
enum DecisionContext: Equatable, Sendable {
    /// From the Money tab or a menu.
    case money
    /// From "Why?" on a mortgage Next Move. "Test it" is available.
    case whyMove
    /// A "Play yourself" life reached the present year.
    case playYourself
}

struct RealLifeDecisionViewState: Equatable, Sendable {
    struct Alternative: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        /// 0 to 1.
        var successRate: Double
    }

    var phase: LoadPhase
    var question: String
    /// The one clear action, for example "Fix for 5 years."
    var headline: String
    var reasons: [String]
    /// For example "7 in 10 twins in similar past periods did better."
    var evidenceSentence: String
    var successRate: Double
    var twinsCount: Int
    var periods: [String]
    var alternatives: [Alternative]
    var sources: [SourceChipState]
    var disclaimer: String

    // Added by W7 for ADR 0018. Defaults keep older call sites valid. See docs/UI_REQUESTS.md.
    var context: DecisionContext = .money
    /// "Your real decision", "Why this move?" or "You reached today".
    var title: String = "Your real decision"
    /// Action id from the API, for example "fix_5y".
    var actionID: String = ""
    /// For example "7 in 10".
    var successText: String = ""
    /// For example "Based on 40 similar lives in 1989-1991, 2006-2008 and 2022-2024."
    var basisSentence: String = ""
    /// True when the screen can open "Test it" for the move.
    var canTestIt: Bool = false
    /// True when any source is sample data.
    var isSampleData: Bool = false
}

struct RealLifeDecisionActions {
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}
    /// Opens "Test it" for the move. Only called when `canTestIt` is true.
    var onTestIt: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
