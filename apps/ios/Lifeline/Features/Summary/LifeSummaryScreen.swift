import SwiftUI

/// Glue: owns `LifeSummaryViewModel` and feeds `LifeSummaryView`.
struct LifeSummaryScreen: View {
    @State private var model: LifeSummaryViewModel
    private let onNewLife: @MainActor () -> Void
    private let onClose: @MainActor () -> Void

    init(
        client: any LifelineClient,
        lifeID: String,
        emoji: String,
        onNewLife: @escaping @MainActor () -> Void,
        onClose: @escaping @MainActor () -> Void
    ) {
        _model = State(initialValue: LifeSummaryViewModel(client: client, lifeID: lifeID, emoji: emoji))
        self.onNewLife = onNewLife
        self.onClose = onClose
    }

    var body: some View {
        LifeSummaryView(state: model.state, actions: model.actions)
            .onAppear {
                model.onNewLife = onNewLife
                model.onClose = onClose
            }
            .task { await model.load() }
    }
}
