import SwiftUI

/// Screens pushed from Money home (ADR 0072).
enum MoneyRoute: Hashable, Identifiable {
    case maths
    case allSpending
    case category(id: String, label: String)

    var id: String {
        switch self {
        case .maths: "maths"
        case .allSpending: "allSpending"
        case let .category(id, _): "category.\(id)"
        }
    }
}

/// Glue for the Money tab (ADR 0072). Owns `MoneyHomeViewModel` and pushes The maths, All spending and a
/// category. Ask Penny opens the Penny tab with the forecast loaded.
struct MoneyHomeScreen: View {
    let client: any LifelineClient
    /// Opens a stored life in the Life tab. Kept for the root's call site; Money home no longer links to Life.
    let onOpenLife: @MainActor (String) -> Void
    @State private var model: MoneyHomeViewModel
    @State private var route: MoneyRoute?
    @State private var navigation = MoneyNavigation.shared
    @Environment(\.appRoutes) private var routes
    /// Bumped by the root after onboarding, sign-out or account deletion.
    @Environment(\.appDataVersion) private var dataVersion

    init(client: any LifelineClient, onOpenLife: @escaping @MainActor (String) -> Void) {
        self.client = client
        self.onOpenLife = onOpenLife
        _model = State(initialValue: MoneyHomeViewModel(client: client))
    }

    var body: some View {
        MoneyHomeView(state: model.state, actions: model.actions)
            .onAppear {
                wireRoutes()
                handleNavigation()
                Task { await model.reloadIfNeeded() }
            }
            .task { await model.loadIfNeeded() }
            .onChange(of: dataVersion) { Task { await model.load() } }
            .onChange(of: navigation.request?.id) { handleNavigation() }
            .navigationDestination(item: $route) { route in
                switch route {
                case .maths:
                    ForecastMathsScreen(client: client, forecast: model.forecast) { [model] in model.show($0) }
                case .allSpending:
                    AllSpendingScreen(client: client)
                case let .category(id, label):
                    CategoryScreen(client: client, category: id, label: label, month: nil)
                }
            }
    }

    private func wireRoutes() {
        let routes = self.routes
        model.onConnectMoney = { routes.openConnectMoney() }
        model.onAskPenny = { routes.askPenny(PennyRoute(screen: .money)) }
        model.onAskPennyForecast = { routes.askPenny(.weeklyBudget) }
        model.onSeeMaths = { route = .maths }
        model.onSeeAllSpending = { route = .allSpending }
        model.onCategory = { id, label in route = .category(id: id, label: label) }
    }

    /// A Penny link asked for a Money screen (`MoneyNavigation`).
    private func handleNavigation() {
        guard let request = navigation.request else { return }
        navigation.clear()
        switch request.destination {
        case .forecast:
            route = nil
        case .theMaths:
            route = .maths
        case .allSpending:
            route = .allSpending
        }
    }
}

/// The one place that builds W7's "Test it" screen (ADR 0018). Not reachable from Money home since ADR 0072;
/// kept so the Test it code and its tests still build.
@MainActor
enum TestItRoute {
    static func screen(
        client: any LifelineClient,
        moveID: String,
        onOpenLife: @escaping @MainActor (String) -> Void,
        onClose: @escaping @MainActor () -> Void,
        onDoThis: (@MainActor (String) -> Void)? = nil
    ) -> some View {
        TestItScreen(
            moveId: moveID,
            load: { moveID, optionIDs in try await client.testNextMove(moveID: moveID, optionIDs: optionIDs) },
            onOpenLife: onOpenLife,
            onClose: onClose,
            onDoThis: onDoThis
        )
    }
}
