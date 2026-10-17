import Foundation

/// The Next Move card: the first element on the Money tab (ADR 0018).
/// Every number comes from `GET /v1/next-move`.
struct NextMoveCardState: Equatable, Sendable {
    struct Option: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var isRecommended: Bool
    }

    struct Move: Equatable, Sendable, Identifiable {
        var id: String
        /// Contract `MoveKind` raw value, for example "fix_mortgage".
        var kind: String
        /// "Fix for 5 years".
        var action: String
        /// "Your deal ends in 165 days".
        var headline: String
        /// GBP per year vs doing nothing. Raw number for `.numericText()`.
        var impactPerYear: Double
        /// "£1,240 a year better off".
        var impactText: String
        /// "Worst past period: £310 a year worse off".
        var worstCaseText: String
        /// 0 to 1.
        var confidence: Double
        /// "7 in 10 twins in similar past periods did better".
        var confidenceLabel: String
        /// "Decide by 31 Mar 2027 (165 days left)". Nil when the move has no deadline.
        var deadlineText: String?
        var daysLeft: Int?
        var sources: [SourceChipState]
        var options: [Option]
        /// "Test it" is shown only when true.
        var isTestable: Bool
        /// "Why?" is shown only when the move has a lesson.
        var hasLesson: Bool
        /// True after "Do this".
        var isInPlan: Bool
    }

    var phase: LoadPhase
    /// "What is my next money move?"
    var question: String
    var top: Move?
    var runnersUp: [Move]
    /// "Tested on 58 past deal ends: right 69% of the time. Always fix for 2 years: 41%."
    var backtestText: String?
    var isSampleData: Bool
    /// The move id that "Do this" is adding now.
    var addingMoveID: String?
    /// "Added to your plan. Your plan is worth £1,240 a year."
    var planMessage: String?
    /// Move to show in focus after a widget link. Nil means the top move.
    var focusedMoveID: String?

    /// The move the card shows: the focused runner-up, or the top move.
    var displayedMove: Move? {
        if let focusedMoveID, let move = runnersUp.first(where: { $0.id == focusedMoveID }) { return move }
        return top
    }
}

struct NextMoveActions {
    /// Opens the "Test it" comparison for a move id (W7 screen).
    var onTestIt: @MainActor (String) -> Void = { _ in }
    /// Opens the lesson for the move's concept plus its 3 evidence points.
    var onWhy: @MainActor (String) -> Void = { _ in }
    /// Adds the move to the plan (`POST /v1/plan`).
    var onDoThis: @MainActor (String) -> Void = { _ in }
    /// Shows a runner-up in the card. Nil goes back to the top move.
    var onFocus: @MainActor (String?) -> Void = { _ in }
    var onOpenPlan: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
