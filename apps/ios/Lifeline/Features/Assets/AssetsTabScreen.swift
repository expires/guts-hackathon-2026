import SwiftUI

/// Glue: owns `AssetsTabViewModel` and feeds `AssetsTabView`.
struct AssetsTabScreen: View {
    @State private var model: AssetsTabViewModel
    private let onClose: @MainActor () -> Void

    init(session: GameSession, onClose: @escaping @MainActor () -> Void = {}) {
        _model = State(initialValue: AssetsTabViewModel(session: session))
        self.onClose = onClose
    }

    var body: some View {
        AssetsTabView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
    }
}
