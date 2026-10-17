import SwiftUI

/// Full-screen routes from the Play tab (no system sheets, ADR 0026 UI fix pass).
enum PlaySheet: String, Identifiable {
    case room, concepts
    var id: String { rawValue }
}

/// Glue for the Play tab (ADR 0016). Rooms run on W7's fixture room (Tier 2 on the backend).
struct PlayScreen: View {
    let session: GameSession
    /// Shows the Life tab.
    let onShowLife: @MainActor () -> Void
    @State private var model: PlayViewModel
    @State private var rooms: RoomLobbyViewModel
    @State private var sheet: PlaySheet?

    init(session: GameSession, onShowLife: @escaping @MainActor () -> Void) {
        self.session = session
        self.onShowLife = onShowLife
        _model = State(initialValue: PlayViewModel(session: session))
        let rooms = RoomLobbyViewModel(client: session.client)
        rooms.loadDemo(RoomsFixtures.demo)
        _rooms = State(initialValue: rooms)
    }

    private var state: PlayViewState {
        var state = model.state
        state.room = rooms.state
        return state
    }

    private var actions: PlayActions {
        var actions = model.actions
        actions.room = rooms.actions
        return actions
    }

    var body: some View {
        PlayView(state: state, actions: actions)
            .onAppear {
                model.onRoute = { route in
                    switch route {
                    case .life: onShowLife()
                    case .rooms: sheet = .room
                    case .concepts: sheet = .concepts
                    }
                }
                rooms.onStart = { _ in sheet = .room }
            }
            .task { await model.load() }
            .refreshable { await model.load() }
            .llCover(item: $sheet) { sheet in
                let close: @MainActor () -> Void = { self.sheet = nil }
                switch sheet {
                case .room: RoomFlowScreen(demo: RoomsFixtures.demo, onClose: close)
                case .concepts:
                    ConceptCollectionScreen(client: session.client, unlockedIDs: session.life?.conceptsUnlocked ?? [], onClose: close)
                }
            }
    }
}
