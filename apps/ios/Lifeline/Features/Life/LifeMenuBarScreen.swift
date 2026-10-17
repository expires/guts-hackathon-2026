import SwiftUI

/// Glue: owns `LifeMenuViewModel` and feeds `LifeMenuBarView`.
struct LifeMenuBarScreen: View {
    @State private var model: LifeMenuViewModel
    private let onOpen: @MainActor (LifeMenuViewState.Menu) -> Void

    init(session: GameSession, onOpen: @escaping @MainActor (LifeMenuViewState.Menu) -> Void) {
        _model = State(initialValue: LifeMenuViewModel(session: session))
        self.onOpen = onOpen
    }

    var body: some View {
        LifeMenuBarView(state: model.state, actions: model.actions)
            .onAppear { model.onOpen = onOpen }
    }
}
