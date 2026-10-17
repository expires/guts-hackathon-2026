import SwiftUI

/// Glue: owns `MoneyHomeViewModel`, routes its cards to the Accounts, Investments, Habits and Test it screens.
struct MoneyHomeScreen: View {
    let client: any LifelineClient
    @Environment(AppCoordinator.self) private var coordinator
    @State private var model: MoneyHomeViewModel
    @State private var testItMoveID: String?

    init(client: any LifelineClient) {
        self.client = client
        _model = State(initialValue: MoneyHomeViewModel(client: client))
    }

    var body: some View {
        MoneyHomeView(state: model.state, actions: actions)
            .task { await model.loadIfNeeded() }
            .onChange(of: coordinator.connectionsVersion) {
                Task { await model.reloadAfterConnectionChange() }
            }
            .onAppear {
                model.nextMove.onTestIt = { testItMoveID = $0 }
            }
            .sheet(item: Binding(get: { testItMoveID.map(TestItRoute.init) }, set: { testItMoveID = $0?.id })) { route in
                TestItScreen(
                    moveId: route.id,
                    load: { [client] moveID, optionIDs in try await client.testNextMove(moveID: moveID, optionIDs: optionIDs) },
                    onClose: { testItMoveID = nil }
                )
            }
    }

    private var actions: MoneyHomeActions {
        var actions = model.actions
        actions.onOpenAccounts = { coordinator.openAccounts() }
        actions.onOpenInvestments = { coordinator.openInvestments() }
        actions.onOpenHabits = { coordinator.openHabits() }
        return actions
    }

    private struct TestItRoute: Identifiable {
        let id: String
    }
}
