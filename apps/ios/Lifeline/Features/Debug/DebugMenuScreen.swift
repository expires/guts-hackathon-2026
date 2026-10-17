import SwiftUI

/// Glue: owns `DebugMenuViewModel` and feeds `DebugMenuView`.
struct DebugMenuScreen: View {
    @State private var model: DebugMenuViewModel
    private let onClose: @MainActor () -> Void

    init(activeKind: ClientKind, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: DebugMenuViewModel(activeKind: activeKind))
        self.onClose = onClose
    }

    var body: some View {
        DebugMenuView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
    }
}
