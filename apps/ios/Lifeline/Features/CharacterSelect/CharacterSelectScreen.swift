import SwiftUI

/// Glue: owns `CharacterSelectViewModel` and feeds `CharacterSelectView`.
struct CharacterSelectScreen: View {
    @State private var model: CharacterSelectViewModel
    private let onRoute: @MainActor (CharacterSelectViewModel.Route) -> Void

    init(session: GameSession, onRoute: @escaping @MainActor (CharacterSelectViewModel.Route) -> Void) {
        _model = State(initialValue: CharacterSelectViewModel(session: session))
        self.onRoute = onRoute
    }

    var body: some View {
        CharacterSelectView(state: model.state, actions: model.actions)
            .onAppear { model.onRoute = onRoute }
            .task { await model.load() }
            .refreshable { await model.load() }
    }
}
