import SwiftUI

/// Deep link `lifeline://join/CODE`: joins the room and shows it full screen.
/// BOSS routes the link here (App/**). Parse the URL with `RoomLink.code(from:)`.
struct RoomJoinScreen: View {
    @State private var model: RoomFlowViewModel
    let code: String
    private let onClose: @MainActor () -> Void

    /// Preferred: shares the room with the Play tab, and your room life plays in the Life tab.
    init(session: GameSession, code: String, onClose: @escaping @MainActor () -> Void = {}) {
        _model = State(initialValue: RoomFlowViewModel.shared(for: session))
        self.code = RoomLink.normalise(code)
        self.onClose = onClose
    }

    /// Client only: makes its own `GameSession`. The room life plays in the room screen only.
    init(client: any LifelineClient, code: String, onClose: @escaping @MainActor () -> Void = {}) {
        _model = State(initialValue: RoomFlowViewModel(game: GameSession(client: client)))
        self.code = RoomLink.normalise(code)
        self.onClose = onClose
    }

    var body: some View {
        RoomFlowScreen(model: model, onClose: onClose)
            .roomObservers(model)
            .task(id: code) { await model.join(code: code, presentCover: false) }
    }
}
