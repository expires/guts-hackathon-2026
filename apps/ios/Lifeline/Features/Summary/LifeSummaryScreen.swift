import SwiftUI

/// Glue: owns `LifeSummaryViewModel` and feeds `LifeSummaryView`.
struct LifeSummaryScreen: View {
    @State private var model: LifeSummaryViewModel
    @Environment(\.llPresentationMode) private var presentation
    @Environment(\.appRoutes) private var routes
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

    private var actions: LifeSummaryActions {
        var actions = model.actions
        actions.onNextMove = {
            onClose()
            routes.selectTab(.money)
        }
        return actions
    }

    var body: some View {
        LifeSummaryView(state: model.state.presented(presentation), actions: actions)
            .onAppear {
                model.onNewLife = onNewLife
                model.onClose = onClose
            }
            .task { await model.load() }
    }
}
