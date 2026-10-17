import Foundation

/// The user's plan: moves they chose with "Do this" (`GET /v1/plan`, ADR 0018).
struct PlanViewState: Equatable, Sendable {
    struct Item: Equatable, Sendable, Identifiable {
        var id: String
        var action: String
        var impactPerYear: Double
        /// "£1,240 a year better off".
        var impactText: String
        var isDone: Bool
        /// "Added 17 Oct 2026".
        var addedText: String
    }

    var phase: LoadPhase
    var items: [Item]
    var totalPerYear: Double
    /// "Your plan is worth £1,240 a year."
    var totalText: String
    var isSampleData: Bool
}

struct PlanActions {
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
