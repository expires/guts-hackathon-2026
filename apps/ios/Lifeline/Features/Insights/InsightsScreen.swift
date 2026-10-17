import SwiftUI

/// Glue: owns `InsightsViewModel` and feeds `InsightsView`. Full screen over the Money tab.
struct InsightsScreen: View {
    @State private var model: InsightsViewModel
    private let onClose: @MainActor () -> Void

    init(client: any LifelineClient, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: InsightsViewModel(client: client))
        self.onClose = onClose
    }

    var body: some View {
        InsightsView(state: model.state, actions: model.actions)
            .task {
                model.onClose = onClose
                await model.load()
            }
    }
}
