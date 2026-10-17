import SwiftUI

/// Sheets from the You tab.
enum YouSheet: String, Identifiable {
    case bank, plan, sources, evaluation, spendAccuracy, store, debug, aiDisclosure
    var id: String { rawValue }
}

/// Glue for the You tab (ADR 0016). Bank connection is W7's `BankConnectScreen`.
struct YouScreen: View {
    let session: GameSession
    @State private var model: YouViewModel
    @State private var sheet: YouSheet?
    @Environment(\.appRoutes) private var routes
    /// Judge mode action waiting for confirmation.
    @State private var judgeConfirm: YouViewModel.Route?
    /// Router action `openConnectMoney()` (BOSS). Wired by `RootScreen`.
    private let onConnectMoney: @MainActor () -> Void

    /// Judge mode routes (BOSS helper: new demo player and demo reset, then onboarding).
    private let onNewPlayer: @MainActor () -> Void
    private let onResetDemo: @MainActor () -> Void

    init(
        session: GameSession,
        onConnectMoney: @escaping @MainActor () -> Void = {},
        onNewPlayer: @escaping @MainActor () -> Void = {},
        onResetDemo: @escaping @MainActor () -> Void = {}
    ) {
        self.session = session
        self.onConnectMoney = onConnectMoney
        self.onNewPlayer = onNewPlayer
        self.onResetDemo = onResetDemo
        _model = State(initialValue: YouViewModel(client: session.client))
    }

    var body: some View {
        YouView(state: model.state, actions: model.actions)
            .onAppear {
                model.onRoute = { route in
                    sheet = switch route {
                    case .bank: .bank
                    case .plan: .plan
                    case .sources: .sources
                    case .evaluation: .evaluation
                    case .spendAccuracy: .spendAccuracy
                    case .store: .store
                    case .debug: .debug
                    case .connectMoney: nil
                    case .askPenny, .newPlayer, .resetDemo, .account: nil
                    case .aiDisclosure: .aiDisclosure
                    }
                    // Opens onboarding at "Connect your money", not at the welcome pages.
                    if route == .connectMoney { routes.openConnectMoney() }
                    if route == .account { routes.openAccount() }
                    // "Ask Penny" switches to the Penny tab (ADR 0051), not a sheet.
                    if route == .askPenny { routes.askPenny(PennyRoute(screen: .other)) }
                    if route == .newPlayer || route == .resetDemo { judgeConfirm = route }
                }
            }
            .confirmationDialog(
                judgeConfirm == .resetDemo ? "Reset the demo?" : "Start as a new player?",
                isPresented: Binding(get: { judgeConfirm != nil }, set: { if !$0 { judgeConfirm = nil } }),
                titleVisibility: .visible
            ) {
                Button(judgeConfirm == .resetDemo ? "Reset demo" : "New player", role: .destructive) {
                    let route = judgeConfirm
                    judgeConfirm = nil
                    if route == .resetDemo { onResetDemo() } else { onNewPlayer() }
                }
                Button("Cancel", role: .cancel) { judgeConfirm = nil }
            } message: {
                Text(judgeConfirm == .resetDemo
                     ? "This clears the demo accounts and rooms, then starts onboarding."
                     : "This starts a fresh demo account and opens onboarding.")
            }
            .task {
                model.conceptsUnlocked = session.life?.conceptsUnlocked.count
                await model.load()
            }
            .llSheet(item: $sheet) { sheet in
                let close: @MainActor () -> Void = { self.sheet = nil }
                switch sheet {
                case .bank: BankConnectScreen(client: session.client, onUseProfile: { _, _ in close() }, onClose: close)
                case .plan: PlanScreen(client: session.client, onClose: close)
                case .sources: SourcesScreen(client: session.client, onClose: close)
                case .evaluation: EvaluationScreen(client: session.client, onClose: close)
                case .spendAccuracy: SpendAccuracyScreen(client: session.client, onClose: close)
                case .store: StoreScreen(session: session, onClose: close)
                case .aiDisclosure: AIDisclosureView(state: .load(), onClose: close)
                case .debug: DebugMenuScreen(activeKind: session.client.kind, onClose: close)
                }
            }
    }
}
