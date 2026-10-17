import Foundation
import Observation

@MainActor
@Observable
final class PeopleTabViewModel {
    private let session: GameSession

    init(session: GameSession) {
        self.session = session
    }

    var state: PeopleTabViewState {
        Self.makeState(life: session.life, isBusy: session.isBusy, outcome: ActionTabSupport.outcome(session))
    }

    var actions: ActionTabActions {
        ActionTabActions(
            onAction: { [weak self] in
                guard let self else { return }
                ActionTabSupport.perform(session, tab: .relationships, actionID: $0)
            },
            onDismissOutcome: { [weak self] in self?.session.dismissOutcome() }
        )
    }

    static func makeState(life: Life?, isBusy: Bool, outcome: OutcomeState?) -> PeopleTabViewState {
        PeopleTabViewState(
            people: (life?.relationships ?? []).map {
                .init(id: $0.id, emoji: $0.emoji, name: $0.name, relation: $0.kind.rawValue.capitalized, closeness: $0.closeness)
            },
            actions: StateMapping.actions(life, tab: .relationships),
            isBusy: isBusy,
            outcome: outcome
        )
    }
}
