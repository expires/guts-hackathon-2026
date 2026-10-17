import SwiftUI

/// Glue: owns `YouViewModel` and routes its rows to sheets.
struct YouScreen: View {
    @Environment(AppCoordinator.self) private var coordinator
    @State private var model: YouViewModel

    init(client: any LifelineClient) {
        _model = State(initialValue: YouViewModel(client: client))
    }

    var body: some View {
        YouView(state: model.state, actions: model.actions)
            .task {
                model.onRoute = { route in
                    switch route {
                    case .bank: coordinator.openAccounts()
                    case .sources: coordinator.sheet = .sources
                    case .store: coordinator.sheet = .store
                    case .debug: coordinator.sheet = .debug
                    case .plan, .evaluation, .spendAccuracy: break
                    }
                }
                await model.load()
            }
            .onChange(of: coordinator.connectionsVersion) { Task { await model.load() } }
    }
}
