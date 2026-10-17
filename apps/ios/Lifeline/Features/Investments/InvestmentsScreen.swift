import SwiftUI

/// Glue: owns `InvestmentsViewModel` and feeds `InvestmentsView`.
struct InvestmentsScreen: View {
    @State private var model: InvestmentsViewModel
    private let onClose: @MainActor () -> Void

    init(client: any LifelineClient, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: InvestmentsViewModel(client: client))
        self.onClose = onClose
    }

    var body: some View {
        InvestmentsView(state: model.state, actions: model.actions)
            .task {
                model.onClose = onClose
                await model.load()
            }
    }
}
