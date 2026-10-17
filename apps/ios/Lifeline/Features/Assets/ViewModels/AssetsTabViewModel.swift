import Foundation
import Observation

@MainActor
@Observable
final class AssetsTabViewModel {
    private let session: GameSession

    init(session: GameSession) {
        self.session = session
    }

    var state: AssetsTabViewState {
        Self.makeState(life: session.life, isBusy: session.isBusy, outcome: ActionTabSupport.outcome(session))
    }

    var actions: ActionTabActions {
        ActionTabActions(
            onAction: { [weak self] in
                guard let self else { return }
                ActionTabSupport.perform(session, tab: .assets, actionID: $0)
            },
            onDismissOutcome: { [weak self] in self?.session.dismissOutcome() }
        )
    }

    static func makeState(life: Life?, isBusy: Bool, outcome: OutcomeState?) -> AssetsTabViewState {
        let items = (life?.assets ?? []).map { asset in
            AssetsTabViewState.Item(
                id: asset.id,
                emoji: emoji(for: asset.kind),
                name: asset.name,
                kindLabel: asset.kind.rawValue.capitalized,
                value: asset.value
            )
        }
        return AssetsTabViewState(
            items: items,
            totalValue: items.map(\.value).reduce(0, +),
            actions: StateMapping.actions(life, tab: .assets),
            isBusy: isBusy,
            outcome: outcome
        )
    }

    static func emoji(for kind: Components.Schemas.Asset.KindPayload) -> String {
        switch kind {
        case .home: "🏠"
        case .car: "🚗"
        case .investment: "📈"
        case .crypto: "🪙"
        case .pension: "🧓"
        case .business: "🏪"
        case .other: "📦"
        }
    }
}
