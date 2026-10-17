import Foundation

/// "Why?" for a Next Move: the 3 evidence points plus the lesson for the move's concept (ADR 0018).
struct NextMoveWhyViewState: Equatable, Sendable {
    struct Evidence: Equatable, Sendable, Identifiable {
        var id: Int
        /// Plain English. Every number in it comes from the engine's `facts`.
        var text: String
        var source: SourceChipState?
    }

    struct LessonPreview: Equatable, Sendable {
        var title: String
        /// Always 2 sentences.
        var sentences: [String]
        /// "You spend £47 a month on 6 subscriptions." Nil without finance data.
        var personal: String?
    }

    /// "Fix for 5 years".
    var action: String
    /// "Your deal ends in 165 days".
    var headline: String
    /// "7 in 10 twins in similar past periods did better".
    var confidenceLabel: String
    var evidence: [Evidence]
    var sources: [SourceChipState]
    /// Load state of the lesson only. The evidence shows at once.
    var lessonPhase: LoadPhase
    /// Nil when the concept has no lesson yet.
    var lesson: LessonPreview?
    var isSampleData: Bool
    /// Mortgage moves also link to the full Real-life Decision screen (W7).
    var hasDecisionDetail: Bool = false
}

struct NextMoveWhyActions {
    /// Opens the full lesson (chart and quiz).
    var onOpenLesson: @MainActor () -> Void = {}
    /// Opens the full Real-life Decision (mortgage moves only).
    var onOpenDecision: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
