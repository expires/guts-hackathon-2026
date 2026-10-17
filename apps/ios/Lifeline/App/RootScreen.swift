import SwiftUI

/// Top-level navigation glue. Character select flow, then the life shell with tabs.
struct RootScreen: View {
    let session: GameSession
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        @Bindable var session = session
        Group {
            switch session.phase {
            case .selecting:
                SelectionFlowScreen(session: session)
                    .transition(.opacity)
            case .playing:
                LifeShellScreen(session: session)
                    .transition(.opacity)
            }
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: session.phase)
        .alert(
            "Something went wrong",
            isPresented: Binding(
                get: { session.errorMessage != nil },
                set: { if !$0 { session.errorMessage = nil } }
            ),
            presenting: session.errorMessage
        ) { _ in
            Button("OK", role: .cancel) { session.errorMessage = nil }
        } message: { message in
            Text(message)
        }
    }
}

/// Routes inside the selection flow.
enum SelectionRoute: Hashable {
    case form(CharacterFormMode)
    case startYear(CharacterChoice)
}

/// Sheets from character select.
enum SelectionSheet: String, Identifiable {
    case store, rooms, sources, debug
    var id: String { rawValue }
}

/// Character select -> (optional form) -> start year picker.
struct SelectionFlowScreen: View {
    let session: GameSession
    @State private var path: [SelectionRoute] = []
    @State private var sheet: SelectionSheet?

    var body: some View {
        NavigationStack(path: $path) {
            CharacterSelectScreen(session: session) { route in
                switch route {
                case let .form(mode): path.append(.form(mode))
                case let .startYear(choice): path.append(.startYear(choice))
                case .store: sheet = .store
                case .rooms: sheet = .rooms
                case .sources: sheet = .sources
                case .debugMenu: sheet = .debug
                }
            }
            .navigationDestination(for: SelectionRoute.self) { route in
                switch route {
                case let .form(mode):
                    CharacterFormScreen(mode: mode, session: session) { choice in path.append(.startYear(choice)) }
                case let .startYear(choice):
                    StartYearPickerScreen(choice: choice, session: session)
                }
            }
        }
        .sheet(item: $sheet) { sheet in
            let close: @MainActor () -> Void = { self.sheet = nil }
            switch sheet {
            case .store: StoreScreen(session: session, onClose: close)
            case .rooms: RoomLobbyScreen(client: session.client, onLeave: close)
            case .sources: SourcesScreen(client: session.client, onClose: close)
            case .debug: DebugMenuScreen(activeKind: session.client.kind, onClose: close)
            }
        }
    }
}
