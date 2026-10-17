import SwiftUI

/// Glue: owns `EventSheetViewModel` and feeds `EventSheetView`.
struct EventSheetScreen: View {
    @State private var model: EventSheetViewModel
    private let onClose: @MainActor () -> Void

    init(session: GameSession, onClose: @escaping @MainActor () -> Void = {}) {
        _model = State(initialValue: EventSheetViewModel(session: session))
        self.onClose = onClose
    }

    var body: some View {
        if let state = model.state {
            EventSheetView(state: state, actions: model.actions)
                .onAppear { model.onClose = onClose }
        }
    }
}
