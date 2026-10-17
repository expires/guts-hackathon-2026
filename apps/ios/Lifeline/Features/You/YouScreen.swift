import SwiftUI

/// Sheets from the You tab.
enum YouSheet: String, Identifiable {
    case bank, plan, sources, evaluation, spendAccuracy, store, debug
    var id: String { rawValue }
}

/// Glue for the You tab (ADR 0016). Bank connection is W7's `BankConnectScreen`.
struct YouScreen: View {
    let session: GameSession
    @State private var model: YouViewModel
    @State private var sheet: YouSheet?

    init(session: GameSession) {
        self.session = session
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
                    }
                }
            }
            .task {
                model.conceptsUnlocked = session.life?.conceptsUnlocked.count
                await model.load()
            }
            .fullScreenCover(item: $sheet) { sheet in
                let close: @MainActor () -> Void = { self.sheet = nil }
                switch sheet {
                case .bank: BankConnectScreen(client: session.client, onUseProfile: { _, _ in close() }, onClose: close)
                case .plan: PlanScreen(client: session.client, onClose: close)
                case .sources: SourcesScreen(client: session.client, onClose: close)
                case .evaluation: EvaluationScreen(client: session.client, onClose: close)
                case .spendAccuracy: SpendAccuracyScreen(client: session.client, onClose: close)
                case .store: StoreScreen(session: session, onClose: close)
                case .debug: DebugMenuScreen(activeKind: session.client.kind, onClose: close)
                }
            }
    }
}
