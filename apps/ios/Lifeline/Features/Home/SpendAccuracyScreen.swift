import SwiftUI

/// Glue: owns `SpendAccuracyViewModel` and feeds `SpendAccuracyView`.
struct SpendAccuracyScreen: View {
    @State private var model: SpendAccuracyViewModel
    private let onClose: @MainActor () -> Void

    init(client: any LifelineClient, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: SpendAccuracyViewModel(client: client))
        self.onClose = onClose
    }

    var body: some View {
        SpendAccuracyView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
            .task { await model.load() }
    }
}
