import SwiftUI

/// App tabs (ADR 0016), in this order. Money is the default.
enum AppTab: String, Hashable, CaseIterable {
    case money, life, play, you

    var title: String {
        switch self {
        case .money: "Money"
        case .life: "Life"
        case .play: "Play"
        case .you: "You"
        }
    }

    /// Tab icon from the Lifeline set: white fill when inactive, colour fill when active.
    var icon: LLIcon {
        switch self {
        case .money: .tabMoney
        case .life: .tabLife
        case .play: .tabPlay
        case .you: .tabYou
        }
    }


    /// The app always opens here. It does not restore the last tab (ADR 0016).
    static let launch: AppTab = .money
}

/// Top-level navigation glue: Money, Life, Play, You.
struct RootScreen: View {
    let session: GameSession
    @State private var selection: AppTab = .launch

    var body: some View {
        // Custom tab bar from the handoff. Every tab stays alive so its state and scroll position persist.
        ZStack {
            ForEach(AppTab.allCases, id: \.self) { tab in
                let isActive = tab == selection
                content(for: tab)
                    .opacity(isActive ? 1 : 0)
                    .allowsHitTesting(isActive)
                    .accessibilityHidden(!isActive)
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            // Setup flows (character select, form, start year) hide the tab bar.
            if !(selection == .life && session.phase == .selecting) {
                LLTabBar(
                    items: AppTab.allCases.map { .init(id: $0.rawValue, title: $0.title, icon: $0.icon) },
                    selection: selection.rawValue
                ) { id in
                    if let tab = AppTab(rawValue: id) { selection = tab }
                }
            }
        }
        .paperBackground()
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

    @ViewBuilder
    private func content(for tab: AppTab) -> some View {
        switch tab {
        case .money:
            NavigationStack {
                MoneyHomeScreen(client: session.client) { lifeID in openLife(lifeID) }
            }
        case .life:
            LifeTabScreen(session: session)
        case .play:
            NavigationStack {
                PlayScreen(session: session) { selection = .life }
            }
        case .you:
            NavigationStack { YouScreen(session: session) }
        }
    }

    /// "Open in Life" from Test it: load the stored life, then show the Life tab.
    private func openLife(_ lifeID: String) {
        Task {
            if await session.openLife(id: lifeID) { selection = .life }
        }
    }
}

/// Life tab: character select when no life runs, otherwise the running life.
struct LifeTabScreen: View {
    let session: GameSession
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
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
        // Store and Rooms are full screens with their own header. Sources and Debug are sheets.
        .llCover(item: $sheet.only { [.store, .rooms].contains($0) }) { sheet in
            let close: @MainActor () -> Void = { self.sheet = nil }
            switch sheet {
            case .rooms: RoomLobbyScreen(client: session.client, onLeave: close)
            default: StoreScreen(session: session, onClose: close)
            }
        }
        .llSheet(item: $sheet.only { [.sources, .debug].contains($0) }) { sheet in
            let close: @MainActor () -> Void = { self.sheet = nil }
            switch sheet {
            case .debug: DebugMenuScreen(activeKind: session.client.kind, onClose: close)
            default: SourcesScreen(client: session.client, onClose: close)
            }
        }
    }

}
