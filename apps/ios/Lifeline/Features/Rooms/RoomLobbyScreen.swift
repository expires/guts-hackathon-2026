import SwiftUI

/// Full-screen Same Life rooms from character select. Shares the room with the Play tab
/// when it gets the same `GameSession`.
struct RoomLobbyScreen: View {
    @State private var model: RoomFlowViewModel
    private let onLeave: @MainActor () -> Void

    init(session: GameSession, onLeave: @escaping @MainActor () -> Void) {
        _model = State(initialValue: RoomFlowViewModel.shared(for: session))
        self.onLeave = onLeave
    }

    /// Older entry point (RootScreen). It makes its own `GameSession`, so the room life does not
    /// show in the Life tab. Prefer `init(session:onLeave:)`.
    init(client: any LifelineClient, onLeave: @escaping @MainActor () -> Void) {
        _model = State(initialValue: RoomFlowViewModel(game: GameSession(client: client)))
        self.onLeave = onLeave
    }

    var body: some View {
        RoomFlowScreen(model: model, onClose: onLeave)
            .roomObservers(model)
    }
}
