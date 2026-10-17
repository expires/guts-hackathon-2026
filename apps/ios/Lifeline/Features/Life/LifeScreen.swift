import SwiftUI

/// Glue: owns `LifeViewModel` and feeds `LifeView`.
struct LifeScreen: View {
    @State private var model: LifeViewModel
    private let onRoute: @MainActor (LifeViewModel.Route) -> Void

    init(session: GameSession, onRoute: @escaping @MainActor (LifeViewModel.Route) -> Void) {
        _model = State(initialValue: LifeViewModel(session: session))
        self.onRoute = onRoute
    }

    var body: some View {
        LifeView(state: model.state, actions: model.actions)
            .onAppear { model.onRoute = onRoute }
    }
}
