import SwiftUI

/// Glue: owns `RoomLobbyViewModel` and feeds `RoomLobbyView`.
struct RoomLobbyScreen: View {
    @State private var model: RoomLobbyViewModel
    private let onLeave: @MainActor () -> Void

    init(client: any LifelineClient, onLeave: @escaping @MainActor () -> Void) {
        _model = State(initialValue: RoomLobbyViewModel(client: client))
        self.onLeave = onLeave
    }

    var body: some View {
        RoomLobbyView(state: model.state, actions: model.actions)
            .onAppear { model.onLeave = onLeave }
    }
}
