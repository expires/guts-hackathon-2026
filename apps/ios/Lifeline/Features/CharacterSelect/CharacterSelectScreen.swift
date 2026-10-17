import SwiftUI

/// Glue: owns `CharacterSelectViewModel` and feeds `CharacterSelectView`.
struct CharacterSelectScreen: View {
    @State private var model: CharacterSelectViewModel
    private let onRoute: @MainActor (CharacterSelectViewModel.Route) -> Void
    private let onClose: (@MainActor () -> Void)?

    init(
        session: GameSession,
        onClose: (@MainActor () -> Void)? = nil,
        onRoute: @escaping @MainActor (CharacterSelectViewModel.Route) -> Void
    ) {
        _model = State(initialValue: CharacterSelectViewModel(session: session))
        self.onRoute = onRoute
        self.onClose = onClose
    }

    private var actions: CharacterSelectActions {
        var actions = model.actions
        actions.onClose = onClose
        return actions
    }

    var body: some View {
        CharacterSelectView(state: model.state, actions: actions)
            .onAppear { model.onRoute = onRoute }
            .task { await model.load() }
            .refreshable { await model.load() }
    }
}
