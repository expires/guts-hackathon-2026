import SwiftUI

/// Glue: owns `ActivitiesViewModel` and feeds `ActivitiesSheetView`.
struct ActivitiesSheetScreen: View {
    @State private var model: ActivitiesViewModel
    private let onClose: @MainActor () -> Void

    init(session: GameSession, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: ActivitiesViewModel(session: session))
        self.onClose = onClose
    }

    var body: some View {
        ActivitiesSheetView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
    }
}
