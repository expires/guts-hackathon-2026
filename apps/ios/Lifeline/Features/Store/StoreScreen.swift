import SwiftUI

/// Glue: owns `StoreViewModel` and feeds `StoreView`.
struct StoreScreen: View {
    @State private var model: StoreViewModel
    private let onClose: @MainActor () -> Void

    init(session: GameSession, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: StoreViewModel(session: session))
        self.onClose = onClose
    }

    var body: some View {
        StoreView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
    }
}
