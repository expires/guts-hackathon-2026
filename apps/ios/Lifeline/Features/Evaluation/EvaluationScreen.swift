import SwiftUI

/// Glue: owns `EvaluationViewModel` and feeds `EvaluationView`.
struct EvaluationScreen: View {
    @State private var model: EvaluationViewModel
    private let onClose: @MainActor () -> Void

    init(client: any LifelineClient, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: EvaluationViewModel(client: client))
        self.onClose = onClose
    }

    var body: some View {
        EvaluationView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
            .task { await model.load() }
    }
}
