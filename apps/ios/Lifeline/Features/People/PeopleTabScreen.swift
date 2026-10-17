import SwiftUI

/// Glue: owns `PeopleTabViewModel` and feeds `PeopleTabView`.
struct PeopleTabScreen: View {
    @State private var model: PeopleTabViewModel
    private let onClose: @MainActor () -> Void

    init(session: GameSession, onClose: @escaping @MainActor () -> Void = {}) {
        _model = State(initialValue: PeopleTabViewModel(session: session))
        self.onClose = onClose
    }

    var body: some View {
        PeopleTabView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
    }
}
