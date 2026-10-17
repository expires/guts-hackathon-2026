import SwiftUI

/// Glue: owns `EventSheetViewModel` and feeds `EventSheetView`.
struct EventSheetScreen: View {
    @State private var model: EventSheetViewModel

    init(session: GameSession) {
        _model = State(initialValue: EventSheetViewModel(session: session))
    }

    var body: some View {
        if let state = model.state {
            EventSheetView(state: state, actions: model.actions)
        }
    }
}
