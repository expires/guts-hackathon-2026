import SwiftUI

/// Glue: owns `LifeViewModel` and feeds `LifeView`.
struct LifeScreen: View {
    @State private var model: LifeViewModel
    private let onRoute: @MainActor (LifeViewModel.Route) -> Void
    private let onExit: (@MainActor () -> Void)?

    init(
        session: GameSession,
        onExit: (@MainActor () -> Void)? = nil,
        onRoute: @escaping @MainActor (LifeViewModel.Route) -> Void
    ) {
        _model = State(initialValue: LifeViewModel(session: session))
        self.onRoute = onRoute
        self.onExit = onExit
    }

    private var actions: LifeActions {
        var actions = model.actions
        actions.onExit = onExit
        return actions
    }

    var body: some View {
        LifeView(state: model.state, actions: actions)
            .onAppear { model.onRoute = onRoute }
    }
}
