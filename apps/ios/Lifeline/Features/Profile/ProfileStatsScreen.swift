import SwiftUI

/// Glue for "Your profile". Loads the stats and reloads when a connection changes.
struct ProfileStatsScreen: View {
    @State private var model: ProfileStatsViewModel
    /// Bumped by the flow after a connect, so the page reloads.
    private let reloadToken: Int
    private let onConnect: @MainActor (ConnectKind?) -> Void
    private let onPlay: @MainActor () -> Void
    private let onClose: @MainActor () -> Void

    init(
        client: any LifelineClient,
        reloadToken: Int = 0,
        onConnect: @escaping @MainActor (ConnectKind?) -> Void,
        onPlay: @escaping @MainActor () -> Void,
        onClose: @escaping @MainActor () -> Void
    ) {
        _model = State(initialValue: ProfileStatsViewModel(client: client))
        self.reloadToken = reloadToken
        self.onConnect = onConnect
        self.onPlay = onPlay
        self.onClose = onClose
    }

    var body: some View {
        ProfileStatsView(state: model.state, actions: model.actions)
            .onAppear {
                model.onConnect = onConnect
                model.onPlay = onPlay
                model.onClose = onClose
            }
            .task(id: reloadToken) { await model.reload() }
    }
}
