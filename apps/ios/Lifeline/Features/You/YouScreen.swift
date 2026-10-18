import SwiftUI

/// Sheets from the You tab.
enum YouSheet: String, Identifiable {
    case bank, plan, sources, evaluation, spendAccuracy, debug, aiDisclosure
    var id: String { rawValue }
}

/// Glue for the You tab (ADR 0016). Bank connection is W7's `BankConnectScreen`.
struct YouScreen: View {
    let session: GameSession
    @State private var model: YouViewModel
    @State private var sheet: YouSheet?
    /// Learn progress for the "Lessons X/48" tile; the same model opens the path (PENNY_V3_BUILD E5).
    @State private var learn: LearnPathViewModel
    @State private var showsLearn = false
    /// You > Connect your money: the connections editor, and You > Your profile: the stats page.
    @State private var showsConnections = false
    @State private var showsProfile = false
    @Environment(\.appRoutes) private var routes
    /// Judge mode action waiting for confirmation.
    @State private var judgeConfirm: YouViewModel.Route?
    /// Router action `openConnectMoney()` (BOSS). Wired by `RootScreen`.
    private let onConnectMoney: @MainActor () -> Void

    /// Judge mode routes (BOSS helper: new demo player and demo reset, then onboarding).
    private let onNewPlayer: @MainActor () -> Void
    private let onResetDemo: @MainActor () -> Void
    /// "Change language" (ADR 0063). RootScreen passes `routes.changeLanguage`.
    private let onChangeLanguage: @MainActor () -> Void

    init(
        session: GameSession,
        onConnectMoney: @escaping @MainActor () -> Void = {},
        onNewPlayer: @escaping @MainActor () -> Void = {},
        onResetDemo: @escaping @MainActor () -> Void = {},
        onChangeLanguage: @escaping @MainActor () -> Void = {}
    ) {
        self.onChangeLanguage = onChangeLanguage
        self.session = session
        self.onConnectMoney = onConnectMoney
        self.onNewPlayer = onNewPlayer
        self.onResetDemo = onResetDemo
        _model = State(initialValue: YouViewModel(client: session.client))
        _learn = State(initialValue: LearnPathViewModel(client: session.client))
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
                    case .debug: .debug
                    case .connectMoney: nil
                    case .askPenny, .newPlayer, .resetDemo, .account, .changeLanguage, .learn, .profile: nil
                    case .aiDisclosure: .aiDisclosure
                    }
                    // The connections editor: Monzo, Trading 212, a statement, your numbers. No student picker.
                    if route == .connectMoney { showsConnections = true }
                    if route == .profile { showsProfile = true }
                    if route == .account { routes.openAccount() }
                    if route == .changeLanguage { onChangeLanguage() }
                    if route == .learn { showsLearn = true }
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
            .task { await learn.load() }
            .onChange(of: learn.entry, initial: true) { _, entry in
                model.lessons = entry.isLoading ? nil : (entry.done, entry.total)
            }
            .llCover(isPresented: $showsConnections) {
                ConnectionsScreen(
                    client: session.client,
                    onChanged: { Task { await model.load() } },
                    onClose: { showsConnections = false }
                )
            }
            .llCover(isPresented: $showsProfile) {
                PlayAsYourselfFlowScreen(session: session, start: .stats) { showsProfile = false }
            }
            .llCover(isPresented: $showsLearn) {
                LearnPathScreen(model: learn, client: session.client) { showsLearn = false }
            }
            .llSheet(item: $sheet) { sheet in
                let close: @MainActor () -> Void = { self.sheet = nil }
                switch sheet {
                case .bank: BankConnectScreen(client: session.client, onUseProfile: { _, _ in close() }, onClose: close)
                case .plan: PlanScreen(client: session.client, onClose: close)
                case .sources: SourcesScreen(client: session.client, onClose: close)
                case .evaluation: EvaluationScreen(client: session.client, onClose: close)
                case .spendAccuracy: SpendAccuracyScreen(client: session.client, onClose: close)
                case .aiDisclosure: AIDisclosureView(state: .load(), onClose: close)
                case .debug:
                    // Debug builds only (PENNY_V3_BUILD F6): Demo and Release never show it.
                    if ClientFactory.isDebugBuild { DebugMenuScreen(activeKind: session.client.kind, onClose: close) }
                }
            }
    }
}
