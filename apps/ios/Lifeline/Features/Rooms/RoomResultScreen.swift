import SwiftUI

/// Glue: owns `RoomResultViewModel` and feeds `RoomResultView`.
struct RoomResultScreen: View {
    @State private var model: RoomResultViewModel
    private let onClose: @MainActor () -> Void

    init(state: RoomResultViewState, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: RoomResultViewModel(state: state))
        self.onClose = onClose
    }

    var body: some View {
        RoomResultView(state: model.state, actions: model.actions)
            .onAppear {
                model.onClose = onClose
                model.onPlayAgain = onClose
            }
    }
}
