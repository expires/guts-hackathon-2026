import SwiftUI

extension PennyRoute {
    /// Ask Penny from the forecast card and The maths (B3.7): a new chat with the forecast loaded,
    /// "Explain my weekly budget" sent.
    static var weeklyBudget: PennyRoute {
        PennyRoute(screen: .forecast, question: L10n.tr("Explain my weekly budget"), title: L10n.tr("My weekly budget"))
    }

    /// "Ask Penny 'what if...'" from The maths: the forecast loaded, no question sent; the user types it.
    static var whatIf: PennyRoute {
        PennyRoute(screen: .forecast, question: nil, title: L10n.tr("What if..."))
    }

    /// "Ask Penny about groceries" from the category screen.
    static func category(_ label: String) -> PennyRoute {
        PennyRoute(screen: .money, question: L10n.tr("Explain my spending on \(label.lowercased())"), title: label)
    }
}

/// Glue for "The maths": owns `ForecastMathsViewModel`, pushes the detailed breakdown, opens Penny.
struct ForecastMathsScreen: View {
    @State private var model: ForecastMathsViewModel
    @State private var showsDetail = false
    @State private var showsSources = false
    private let client: any LifelineClient
    @Environment(\.appRoutes) private var routes
    @Environment(\.dismiss) private var dismiss
    let onForecastChanged: @MainActor (Forecast) -> Void

    init(client: any LifelineClient, forecast: Forecast?, onForecastChanged: @escaping @MainActor (Forecast) -> Void = { _ in }) {
        self.client = client
        _model = State(initialValue: ForecastMathsViewModel(client: client, forecast: forecast))
        self.onForecastChanged = onForecastChanged
    }

    var body: some View {
        ForecastMathsView(state: model.state, actions: model.actions)
            .onAppear {
                let routes = self.routes
                model.onBack = { dismiss() }
                model.onDetail = { showsDetail = true }
                model.onSources = { showsSources = true }
                model.onAskPenny = { routes.askPenny(.weeklyBudget) }
                model.onAskWhatIf = { routes.askPenny(.whatIf) }
                model.onForecastChanged = onForecastChanged
            }
            .task { if model.forecast == nil { await model.load() } }
            .navigationDestination(isPresented: $showsDetail) {
                if let forecast = model.forecast {
                    ForecastBreakdownView(state: .make(forecast)) { showsDetail = false }
                }
            }
            .navigationDestination(isPresented: $showsSources) {
                SourcesHubScreen(client: client)
            }
    }
}

/// Glue for "All spending": owns `AllSpendingViewModel`, pushes a category.
struct AllSpendingScreen: View {
    let client: any LifelineClient
    @State private var model: AllSpendingViewModel
    @State private var category: CategoryRoute?
    @Environment(\.dismiss) private var dismiss

    struct CategoryRoute: Hashable, Identifiable {
        var id: String
        var label: String
        var month: String?
    }

    init(client: any LifelineClient) {
        self.client = client
        _model = State(initialValue: AllSpendingViewModel(client: client))
    }

    var body: some View {
        AllSpendingView(state: model.state, actions: model.actions)
            .onAppear {
                model.onBack = { dismiss() }
                model.onCategory = { [model] id, month in
                    let label = model.state.pie.flatMap { pie in (pie.slices + pie.fixed).first { $0.id == id }?.label } ?? id
                    category = CategoryRoute(id: id, label: label, month: month)
                }
            }
            .task { await model.load() }
            .navigationDestination(item: $category) { route in
                CategoryScreen(client: client, category: route.id, label: route.label, month: route.month)
            }
    }
}

/// Glue for one category: owns `CategoryDetailViewModel`, opens Penny about it.
struct CategoryScreen: View {
    @State private var model: CategoryDetailViewModel
    @Environment(\.appRoutes) private var routes
    @Environment(\.dismiss) private var dismiss

    init(client: any LifelineClient, category: String, label: String, month: String?) {
        _model = State(initialValue: CategoryDetailViewModel(client: client, category: category, label: label, month: month))
    }

    var body: some View {
        CategoryDetailView(state: model.state, actions: model.actions)
            .onAppear {
                let routes = self.routes
                model.onBack = { dismiss() }
                model.onAskPenny = { routes.askPenny(.category($0)) }
            }
            .task { await model.load() }
    }
}
