import SwiftUI

/// Glue: owns `RewindViewModel`. Shows the picker, then the result.
struct RewindScreen: View {
    @State private var model: RewindViewModel
    private let onClose: @MainActor () -> Void
    private let onBuyPass: @MainActor () -> Void

    /// - Parameter decisionID: the decision to show first (for example from the Lesson). Nil shows the newest.
    init(
        session: GameSession,
        decisionID: String? = nil,
        onClose: @escaping @MainActor () -> Void,
        onBuyPass: @escaping @MainActor () -> Void
    ) {
        _model = State(initialValue: RewindViewModel(session: session, decisionID: decisionID))
        self.onClose = onClose
        self.onBuyPass = onBuyPass
    }

    var body: some View {
        Group {
            if let result = model.result {
                RewindResultView(state: result, onContinue: onClose)
            } else {
                RewindPickerView(state: model.pickerState, actions: model.actions)
            }
        }
        .onAppear {
            model.onClose = onClose
            model.onBuyPass = onBuyPass
        }
    }
}
