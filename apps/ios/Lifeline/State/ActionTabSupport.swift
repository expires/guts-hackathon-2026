import Foundation

/// Shared helpers for the tab ViewModels (Job, Assets, People, Money, Activities).
@MainActor
enum ActionTabSupport {
    static func perform(_ session: GameSession, tab: ActionRequest.TabPayload, actionID: String) {
        Task { await session.act(tab: tab, actionID: actionID) }
    }

    static func outcome(_ session: GameSession) -> OutcomeState? {
        session.lastOutcome.map(StateMapping.outcome)
    }
}
