import SwiftUI

/// Glue: owns `PlanViewModel` and feeds `PlanView`.
struct PlanScreen: View {
    @State private var model: PlanViewModel
    private let onClose: @MainActor () -> Void

    init(client: any LifelineClient, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: PlanViewModel(client: client))
        self.onClose = onClose
    }

    var body: some View {
        PlanView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
            .task { await model.load() }
    }
}
