import Foundation
import Observation

/// Builds the Life tab menu bar from `available_actions`.
@MainActor
@Observable
final class LifeMenuViewModel {
    private let session: GameSession
    @ObservationIgnored var onOpen: @MainActor (LifeMenuViewState.Menu) -> Void = { _ in }

    init(session: GameSession) {
        self.session = session
    }

    var state: LifeMenuViewState { Self.makeState(life: session.life) }

    var actions: LifeMenuActions {
        LifeMenuActions(onOpen: { [weak self] in self?.onOpen($0) })
    }

    static func makeState(life: Life?) -> LifeMenuViewState {
        func count(_ tab: Components.Schemas.AvailableAction.TabPayload) -> Int {
            (life?.availableActions ?? []).filter { $0.tab == tab && ($0.enabled ?? true) }.count
        }
        return LifeMenuViewState(
            items: [
                .init(menu: .job, title: "Job", icon: .job, count: count(.job)),
                .init(menu: .assets, title: "Assets", icon: .home, count: count(.assets)),
                .init(menu: .people, title: "People", icon: .relationships, count: count(.relationships)),
                .init(menu: .money, title: "Money", icon: .savings, count: count(.money)),
                .init(menu: .activities, title: "Activities", icon: .activities, count: count(.activities)),
            ],
            isEnabled: life?.alive ?? false
        )
    }
}
