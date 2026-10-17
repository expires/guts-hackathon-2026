import SwiftUI

/// Glue: owns `JobTabViewModel` and feeds `JobTabView`.
struct JobTabScreen: View {
    @State private var model: JobTabViewModel
    private let onClose: @MainActor () -> Void

    init(session: GameSession, onClose: @escaping @MainActor () -> Void = {}) {
        _model = State(initialValue: JobTabViewModel(session: session))
        self.onClose = onClose
    }

    var body: some View {
        JobTabView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
    }
}
