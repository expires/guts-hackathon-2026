import SwiftUI

/// Top-level navigation glue (ADR 0016): Money (default), Life (the game), You.
/// Also owns deep links: `lifeline://connected?...` after the Monzo sign-in in Safari.
struct RootScreen: View {
    let session: GameSession
    @State private var coordinator = AppCoordinator()
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        @Bindable var session = session
        @Bindable var coordinator = coordinator
        TabView(selection: $coordinator.selectedTab) {
            Tab("Money", systemImage: "sterlingsign.circle", value: AppTab.money) {
                NavigationStack { MoneyHomeScreen(client: session.client) }
            }
            Tab("Life", systemImage: "heart.text.square", value: AppTab.life) {
                lifeFlow
                    // The game has its own tab bar while a life is running.
                    .toolbarVisibility(session.phase == .playing ? .hidden : .automatic, for: .tabBar)
            }
            Tab("You", systemImage: "person.crop.circle", value: AppTab.you) {
                NavigationStack { YouScreen(client: session.client) }
            }
        }
        .onOpenURL { coordinator.handle($0) }
        .sheet(item: $coordinator.sheet) { sheet in
            sheetContent(sheet)
        }
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
        // Outermost on purpose: sheet content inherits the environment from where `.sheet` sits,
        // so applying this inside the sheet modifier left AccountsScreen without a coordinator
        // (SwiftUI traps on a missing @Environment(AppCoordinator.self)).
        .environment(coordinator)
    }

    private var lifeFlow: some View {
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
    }

    @ViewBuilder
    private func sheetContent(_ sheet: AppSheet) -> some View {
        let close: @MainActor () -> Void = { coordinator.sheet = nil }
        switch sheet {
        case .accounts:
            AccountsScreen(client: session.client, onConnectionsChanged: { coordinator.connectionsChanged() }, onClose: close)
        case .investments:
            InvestmentsScreen(client: session.client, onClose: close)
        case .habits:
            HabitsScreen(client: session.client, onClose: close)
        case .sources:
            SourcesScreen(client: session.client, onClose: close)
        case .store:
            StoreScreen(session: session, onClose: close)
        case .debug:
            DebugMenuScreen(activeKind: session.client.kind, onClose: close)
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
