import SwiftUI

/// Glue: owns `SourcesViewModel` and feeds `SourcesView`.
struct SourcesScreen: View {
    @State private var model: SourcesViewModel
    private let onClose: @MainActor () -> Void

    init(client: any LifelineClient, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: SourcesViewModel(client: client))
        self.onClose = onClose
    }

    var body: some View {
        SourcesView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
            .task { await model.load() }
    }
}
