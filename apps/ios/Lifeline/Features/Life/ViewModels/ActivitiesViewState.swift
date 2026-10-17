import Foundation

/// Activities sheet (ADR 0009): actions with `tab = activities`.
struct ActivitiesViewState: Equatable, Sendable {
    var actions: [ActionItemState]
    var isBusy: Bool
    var outcome: OutcomeState?
}
