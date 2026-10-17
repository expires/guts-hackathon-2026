import SwiftUI

/// App tabs (ADR 0048), in this order. Money is the default. Life lives inside Play ("Play solo").
enum AppTab: String, Hashable, CaseIterable {
    case money, penny, play, you

    var title: String {
        switch self {
        case .money: "Money"
        case .penny: "Penny"
        case .play: "Play"
        case .you: "You"
        }
    }

    /// Tab icon from the Lifeline set: white fill when inactive, colour fill when active.
    var icon: LLIcon {
        switch self {
        case .money: .tabMoney
        case .penny: .pennySmiling
        case .play: .tabPlay
        case .you: .tabYou
        }
    }


    /// The app always opens here. It does not restore the last tab (ADR 0016).
    static let launch: AppTab = .money
}

/// Top-level navigation glue: onboarding gate, then Money, Life, Play, You.
/// Also presents the app-wide routes (`AppRoutes`): Ask Penny, onboarding at "Connect your money",
/// account actions and room join links (`lifeline://join/CODE`).
struct RootScreen: View {
    /// Owns the game session and the Penny chat, so judge mode ("New player", "Reset demo") can replace them.
    @State private var router: AppRouter
    @AppStorage("llPresentationMode") private var presentationMode = false

    init(session: GameSession) {
        _router = State(initialValue: AppRouter(session: session))
    }

    /// The current player's session. Replaced by "New player" (new device id, new client) and "Reset demo".
    private var session: GameSession { router.session }
    /// One Penny chat per player (ADR 0051). "Ask Penny" anywhere loads its context here.
    private var penny: PennyTabModel { router.pennyModel }

    private var selection: AppTab { router.selection }

    var body: some View {
        Group {
            switch router.gate {
            case .checking:
                // Short wait for GET /v1/me. Never an empty Money tab before the gate decides.
                Theme.Palette.paper.ignoresSafeArea()
            case .onboarding:
                FeatureSlots.onboarding(client: session.client, start: .welcome) {
                    Task { await router.finishOnboarding(client: session.client) }
                }
            case .ready:
                tabs
            }
        }
        // A new player rebuilds every screen, so no tab keeps the previous player's state.
        .id(router.sessionID)
        .environment(\.appRoutes, router.routes)
        .environment(\.appDataVersion, router.dataVersion)
        .environment(\.appSelectedTab, router.selection)
        .task { await router.checkGate(client: session.client) }
        .onOpenURL { url in router.handle(url: url) }
        // "Ask Penny" switches to the Penny tab with the context loaded (ADR 0048), not a sheet.
        .onChange(of: router.penny) { _, route in
            guard let route else { return }
            router.penny = nil
            router.selection = .penny
            penny.ask(FeatureSlots.pennyContext(route))
        }
        .background {
            Color.clear.llCover(item: $router.onboarding) { start in
                FeatureSlots.onboarding(client: session.client, start: start) {
                    Task { await router.finishOnboarding(client: session.client) }
                }
            }
        }
        .background {
            Color.clear.llSheet(isPresented: $router.showsAccount) {
                FeatureSlots.account(
                    client: session.client,
                    onSignedOut: { Task { await router.signedOut(client: session.client) } },
                    onClose: { router.showsAccount = false }
                )
                .environment(\.appRoutes, router.routes)
            }
        }
        // Room join (deep link or routes.joinRoom): Play tab, then W9's shared room flow opens its room cover.
        .onChange(of: router.join) { _, route in
            guard let route else { return }
            router.join = nil
            router.selection = .play
            Task { await RoomFlowViewModel.shared(for: session).join(code: route.code) }
        }
        // Presentation mode (You tab toggle): rounds money app-wide, including sheets and covers.
        .llPresentationMode(presentationMode)
    }

    private var tabs: some View {
        // Custom tab bar from the handoff. Every tab stays alive so its state and scroll position persist.
        // A VStack (not `.safeAreaInset`): the content frame shrinks, so every NavigationStack lays out
        // above the bar, also right after the bar appears at the end of a setup flow.
        VStack(spacing: 0) {
            ZStack {
                ForEach(AppTab.allCases, id: \.self) { tab in
                    let isActive = tab == selection
                    content(for: tab)
                        .opacity(isActive ? 1 : 0)
                        .allowsHitTesting(isActive)
                        .accessibilityHidden(!isActive)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            // Setup flows (character select, form, start year) hide the tab bar.
            if showsTabBar {
                LLTabBar(
                    items: AppTab.allCases.map { .init(id: $0.rawValue, title: $0.title, icon: $0.icon) },
                    selection: selection.rawValue
                ) { id in
                    if let tab = AppTab(rawValue: id) { router.selection = tab }
                }
            }
        }
        .paperBackground()
        .onPreferenceChange(SetupDepthKey.self) { setupDepth = $0 }
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

    /// Depth of the Life setup flow (0 = Choose a life). Reported by SelectionFlowScreen.
    @State private var setupDepth = 0

    /// Choose a life keeps the tab bar. Only the pushed form and start-year screens hide it
    /// (Life is pushed inside Play; those screens have their own back button).
    private var showsTabBar: Bool {
        !(selection == .play && session.phase == .selecting && setupDepth > 0)
    }


    @ViewBuilder
    private func content(for tab: AppTab) -> some View {
        switch tab {
        case .money:
            NavigationStack {
                MoneyHomeScreen(client: session.client) { lifeID in openLife(lifeID) }
            }
        case .penny:
            PennyTab(model: penny) { _ in router.selection = .money }
        case .play:
            NavigationStack {
                PlayScreen(session: session) {}
            }
        case .you:
            NavigationStack {
                YouScreen(
                    session: session,
                    onConnectMoney: { router.onboarding = .connect },
                    onNewPlayer: { router.routes.newPlayer() },
                    onResetDemo: { router.routes.resetDemo() }
                )
            }
        }
    }

    /// "Open in Life" from Test it: load the stored life, then show the Life tab.
    private func openLife(_ lifeID: String) {
        Task {
            if await session.openLife(id: lifeID) { router.selection = .play }
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

/// How deep the Life setup flow is pushed (0 = Choose a life). Read by RootScreen to show or hide the tab bar.
struct SetupDepthKey: PreferenceKey {
    static let defaultValue = 0
    static func reduce(value: inout Int, nextValue: () -> Int) { value = max(value, nextValue()) }
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
        .preference(key: SetupDepthKey.self, value: path.count)
        // Store and Rooms are full screens with their own header. Sources and Debug are sheets.
        .llCover(item: $sheet.only { [.store, .rooms].contains($0) }) { sheet in
            let close: @MainActor () -> Void = { self.sheet = nil }
            switch sheet {
            case .rooms: RoomLobbyScreen(session: session, onLeave: close)
            default: StoreScreen(session: session, onClose: close)
            }
        }
        .background {
            Color.clear.llSheet(item: $sheet.only { [.sources, .debug].contains($0) }) { sheet in
                let close: @MainActor () -> Void = { self.sheet = nil }
                switch sheet {
                case .debug: DebugMenuScreen(activeKind: session.client.kind, onClose: close)
                default: SourcesScreen(client: session.client, onClose: close)
                }
            }
        }
    }

}
