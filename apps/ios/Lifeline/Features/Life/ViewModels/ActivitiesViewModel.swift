import Foundation
import Observation

@MainActor
@Observable
final class ActivitiesViewModel {
    private let session: GameSession
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(session: GameSession) {
        self.session = session
    }

    var state: ActivitiesViewState {
        ActivitiesViewState(
            actions: StateMapping.actions(session.life, tab: .activities),
            isBusy: session.isBusy,
            outcome: ActionTabSupport.outcome(session)
        )
    }

    var actions: ActionTabActions {
        ActionTabActions(
            onAction: { [weak self] in
                guard let self else { return }
                ActionTabSupport.perform(session, tab: .activities, actionID: $0)
                onClose()
            },
            onDismissOutcome: { [weak self] in self?.session.dismissOutcome() },
            onClose: { [weak self] in self?.onClose() }
        )
    }
}
