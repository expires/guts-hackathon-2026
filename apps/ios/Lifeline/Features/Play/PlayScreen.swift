import SwiftUI

/// Full-screen routes from the Play tab (no system sheets, ADR 0026 UI fix pass).
enum PlaySheet: String, Identifiable {
    case concepts
    case solo
    /// The Learn course path (ADR 0068).
    case learn
    var id: String { rawValue }
}

/// Glue for the Play tab (PENNY_V3_BUILD F4): Play with friends, Learn, Join, Circles. Play solo,
/// challenges and collection only with `FeatureFlags.showsCutFeatures`.
struct PlayScreen: View {
    let session: GameSession
    /// Kept for RootScreen. Play solo now opens inside the Play tab.
    let onShowLife: @MainActor () -> Void
    @State private var model: PlayViewModel
    @State private var sheet: PlaySheet?
    @Bindable private var rooms: RoomFlowViewModel
    @State private var circles: CirclesViewModel
    /// Learn course progress (ADR 0068): the Play card and the path share it.
    @State private var learn: LearnPathViewModel
    @Environment(\.appSelectedTab) private var selectedTab
    @Environment(\.appRoutes) private var routes

    init(session: GameSession, onShowLife: @escaping @MainActor () -> Void = {}) {
        self.session = session
        self.onShowLife = onShowLife
        _model = State(initialValue: PlayViewModel(session: session))
        let rooms = RoomFlowViewModel.shared(for: session)
        self.rooms = rooms
        _circles = State(initialValue: CirclesViewModel(service: rooms.play, isSampleData: session.client.kind == .mock))
        _learn = State(initialValue: LearnPathViewModel(client: session.client))
    }

    private var state: PlayViewState {
        var state = model.state
        state.rooms = rooms.entryState
        state.circles = circles.state
        state.learn = learn.entry
        state.showsCutFeatures = FeatureFlags.showsCutFeatures
        return state
    }

    private var actions: PlayActions {
        var actions = model.actions
        actions.rooms = rooms.entryActions
        actions.circles = circles.actions
        actions.onPlaySolo = { sheet = .solo }
        actions.onPlayWithFriends = { Task { await rooms.openLobby() } }
        actions.onJoin = { rooms.openScanner() }
        actions.onOpenLearn = { sheet = .learn }
        // The concepts collection is the Learn course now (ADR 0068).
        actions.onOpenConcepts = { sheet = .learn }
        return actions
    }

    /// True for every tab except Play.
    static func closesCovers(for tab: AppTab) -> Bool { tab != .play }

    var body: some View {
        PlayView(state: state, actions: actions)
            .onAppear {
                model.onRoute = { route in
                    switch route {
                    case .life: if FeatureFlags.showsCutFeatures { sheet = .solo }
                    case .rooms: rooms.isPresented = true
                    case .concepts: sheet = .learn
                    case .money: routes.selectTab(.money)
                    }
                }
                // "Open in the Life tab" from a live room: close the room cover, then show the life.
                rooms.onOpenLife = {
                    // The full Life game is cut (PENNY_V3_BUILD F2).
                    guard FeatureFlags.showsCutFeatures else { return }
                    Task {
                        try? await Task.sleep(for: .milliseconds(450))
                        sheet = .solo
                    }
                }
            }
            // A life opened elsewhere (Money tab "Open in Life") shows here, unless it is the room life.
            .onChange(of: session.life?.id) { _, id in
                guard FeatureFlags.showsCutFeatures, let id, id != rooms.myLifeID, rooms.session.room?.status != .playing, !rooms.isPresented else { return }
                sheet = .solo
            }
            // V4 F4-1: a switch to another tab (for example "Ask Penny") closes the Play covers.
            // The running life stays in the session, so Play solo resumes it.
            .onChange(of: selectedTab) { _, tab in
                guard Self.closesCovers(for: tab) else { return }
                sheet = nil
                rooms.hideCovers()
            }
            .task { await model.load() }
            .task { await learn.load() }
            // Circles change when a friend joins on another phone: reload every 10 s while Play is open.
            .task {
                await circles.load()
                while !Task.isCancelled {
                    try? await Task.sleep(for: .seconds(10))
                    guard !Task.isCancelled else { break }
                    await circles.load()
                }
            }
            .refreshable {
                async let play: Void = model.load()
                async let friends: Void = circles.load()
                async let lessons: Void = learn.load()
                _ = await (play, friends, lessons)
            }
            .roomObservers(rooms)
            .llCover(item: $sheet) { sheet in
                switch sheet {
                case .concepts:
                    ConceptCollectionScreen(client: session.client, unlockedIDs: session.life?.conceptsUnlocked ?? []) { self.sheet = nil }
                case .solo:
                    PlaySoloScreen(session: session) { self.sheet = nil }
                case .learn:
                    LearnPathScreen(model: learn, client: session.client) { self.sheet = nil }
                }
            }
            .background {
                Color.clear.llCover(isPresented: $rooms.isPresented) {
                    RoomFlowScreen(model: rooms) { rooms.isPresented = false }
                }
            }
            .background {
                Color.clear.roomScanner(model: rooms)
            }
    }
}
