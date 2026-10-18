import SwiftUI

/// "Play as yourself" (Play tab) and "Your profile" (You tab): who you are playing as, the connect step, the
/// stats page, then the game. One navigation stack. The Play tab starts at the profile picker; the You tab starts
/// at the stats page. The connect step is the same `ConnectionsScreen` the You tab's "Connect your money" opens.
struct PlayAsYourselfFlowScreen: View {
    enum Start { case picker, stats }

    enum Route: Hashable {
        case connect(ConnectKind?)
        case stats
    }

    let session: GameSession
    let start: Start
    let onClose: @MainActor () -> Void

    @State private var path: [Route]
    @State private var reloadToken = 0
    @State private var showsGame = false
    @State private var picker: ProfilePickerViewModel

    init(session: GameSession, start: Start = .picker, initialPath: [Route] = [], onClose: @escaping @MainActor () -> Void) {
        self.session = session
        self.start = start
        self.onClose = onClose
        _path = State(initialValue: initialPath)
        _picker = State(initialValue: ProfilePickerViewModel(api: .from(client: session.client)))
    }

    var body: some View {
        NavigationStack(path: $path) {
            root
                .navigationDestination(for: Route.self) { route in
                    switch route {
                    case let .connect(kind):
                        ConnectionsScreen(
                            client: session.client,
                            continueTitle: L10n.tr("Continue"),
                            highlighted: kind,
                            onChanged: { reloadToken += 1 },
                            onContinue: { continueToStats() },
                            onClose: { if !path.isEmpty { path.removeLast() } }
                        )
                    case .stats:
                        stats
                    }
                }
        }
        .llCover(isPresented: $showsGame) {
            PlayYourselfGameScreen(session: session) { showsGame = false }
        }
    }

    @ViewBuilder private var root: some View {
        switch start {
        case .picker:
            ProfilePickerScreen(model: picker) { event in
                switch event {
                case .you: path.append(.connect(nil))
                case .sample:
                    reloadToken += 1
                    path.append(.stats)
                case .close: onClose()
                }
            }
        case .stats:
            stats
        }
    }

    private var stats: some View {
        ProfileStatsScreen(
            client: session.client,
            reloadToken: reloadToken,
            onConnect: { kind in path.append(.connect(kind)) },
            onPlay: { showsGame = true },
            onClose: {
                // The first page closes the flow. A pushed page goes back.
                if path.isEmpty { onClose() } else { path.removeLast() }
            }
        )
    }

    /// "Continue" on the connect step: back to the stats page, or forward to it the first time.
    private func continueToStats() {
        if let index = path.lastIndex(of: .stats) {
            path.removeSubrange((index + 1)...)
        } else if start == .stats {
            path.removeAll()
        } else {
            path.append(.stats)
        }
    }
}

/// Glue for "Who are you playing as?".
struct ProfilePickerScreen: View {
    enum Event { case you, sample, close }

    @State private var model: ProfilePickerViewModel
    private let onEvent: @MainActor (Event) -> Void

    init(model: ProfilePickerViewModel, onEvent: @escaping @MainActor (Event) -> Void) {
        _model = State(initialValue: model)
        self.onEvent = onEvent
    }

    var body: some View {
        ProfilePickerView(state: model.state, actions: model.actions)
            .task { await model.load() }
            .onAppear {
                model.onPickYou = { onEvent(.you) }
                model.onPickedSample = { onEvent(.sample) }
                model.onClose = { onEvent(.close) }
            }
    }
}

/// The existing "Play yourself" game, seeded from the user's own data: the About you form is prefilled from the
/// finance profile, then the start year, then the life.
struct PlayYourselfGameScreen: View {
    let session: GameSession
    let onClose: @MainActor () -> Void
    @State private var path: [SelectionRoute] = []
    @State private var didReset = false

    var body: some View {
        Group {
            if session.phase == .playing {
                LifeShellScreen(session: session, onExit: onClose)
            } else {
                NavigationStack(path: $path) {
                    CharacterFormScreen(mode: .playYourself, session: session) { choice in path.append(.startYear(choice)) }
                        .overlay(alignment: .topTrailing) {
                            HeaderSquareButton(kind: .close, identifier: "playYourself.close", action: onClose)
                                .padding(.horizontal, Theme.Spacing.margin)
                                .padding(.top, Theme.Spacing.s)
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
            }
        }
        .onAppear {
            // Always a new life as yourself, even when another life is open.
            guard !didReset else { return }
            didReset = true
            if session.phase == .playing { session.newLife() }
        }
        .sessionErrorAlert(session)
    }
}
