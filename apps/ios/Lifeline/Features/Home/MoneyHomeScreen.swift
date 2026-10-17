import SwiftUI

/// Sheets the Money tab can open.
enum MoneyHomeSheet: Identifiable {
    case testIt(moveID: String)
    case why(Move, isSampleData: Bool, atSources: Bool = false)
    case plan
    case accuracy
    case guess

    var id: String {
        switch self {
        case let .testIt(moveID): "testIt.\(moveID)"
        case let .why(move, _, atSources): "why.\(move.id).\(atSources)"
        case .plan: "plan"
        case .accuracy: "accuracy"
        case .guess: "guess"
        }
    }

    /// Full screens have their own header and back button. The others show as sheets.
    var isFullScreen: Bool {
        switch self {
        case .testIt, .guess: true
        case .why, .plan, .accuracy: false
        }
    }
}

/// Glue for the Money tab (ADR 0016, 0018). Owns `MoneyHomeViewModel` and routes the
/// Next Move buttons: Test it (W7 `TestItScreen`), Why? and the plan.
struct MoneyHomeScreen: View {
    let client: any LifelineClient
    /// Opens a stored life in the Life tab ("Open in Life" on a Test it option).
    let onOpenLife: @MainActor (String) -> Void
    @State private var model: MoneyHomeViewModel
    @State private var sheet: MoneyHomeSheet?
    @State private var detail: MoneyDetail?
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
                Task { await model.reloadIfNeeded() }
            }
            .task { await model.loadIfNeeded() }
            .onChange(of: dataVersion) { Task { await model.load() } }
            // Test it and Guess my spend are full screens with their own header. The rest are sheets.
            .llCover(item: $sheet.only(\.isFullScreen)) { sheet in
                content(for: sheet).environment(\.dataBadgeText, model.state.badgeText)
            }
            // Each presenter sits on its own view, so the two full-screen covers never share one host.
            .background {
                Color.clear.llSheet(item: $sheet.only { !$0.isFullScreen }) { sheet in
                    content(for: sheet).environment(\.dataBadgeText, model.state.badgeText)
                }
            }
            .navigationDestination(item: $detail) { detail in
                MoneyDetailsView(
                    state: model.widgets.state, detail: detail, actions: model.widgets.actions,
                    nextMoveLink: MoneyWidgetsViewModel.topMoveLink(moves: model.nextMove.moves)
                ) { self.detail = nil }
                .environment(\.dataBadgeText, model.state.badgeText)
            }
            // Last, so the sheets, covers and detail screens above all read the badge text (F2-1).
            .environment(\.dataBadgeText, model.state.badgeText)
    }

    private func wireRoutes() {
        model.nextMove.onTestIt = { present(.testIt(moveID: $0)) }
        model.nextMove.onWhy = { [model] move in present(.why(move, isSampleData: model.nextMove.state.isSampleData)) }
        model.nextMove.onWhySources = { [model] move in present(.why(move, isSampleData: model.nextMove.state.isSampleData, atSources: true)) }
        model.nextMove.onOpenPlan = { present(.plan) }
        model.guess.onOpenAccuracy = { present(.accuracy) }
        model.onOpenGuess = { present(.guess) }
        model.onOpenDetail = { detail = $0 }
        // "Your next move" from Guess my spend: close it and show the top move on the hub.
        model.guess.onShowMove = { [model] _ in
            sheet = nil
            model.nextMove.focus(nil)
        }
        let routes = self.routes
        model.onConnectMoney = { routes.openConnectMoney() }
        model.onAskPenny = { moveID in
            routes.askPenny(moveID.map { PennyRoute(screen: .nextMove, nextMoveID: $0, question: "Why this move?") } ?? PennyRoute(screen: .money))
        }
    }

    /// Shows `next`. When another sheet is open, closes it first and waits for its exit animation,
    /// so the two presenters (`llSheet`, `llCover`) never present at the same time.
    private func present(_ next: MoneyHomeSheet) {
        guard sheet != nil else {
            sheet = next
            return
        }
        sheet = nil
        Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(450))
            sheet = next
        }
    }

    @ViewBuilder
    private func content(for sheet: MoneyHomeSheet) -> some View {
        let close: @MainActor () -> Void = { self.sheet = nil }
        switch sheet {
        case let .testIt(moveID):
            TestItRoute.screen(client: client, moveID: moveID, onOpenLife: { lifeID in
                self.sheet = nil
                onOpenLife(lifeID)
            }, onClose: close, onDoThis: { id in
                Task { await model.nextMove.addToPlan(moveID: id) }
            })
        case let .why(move, isSampleData, atSources):
            NextMoveWhyScreen(client: client, move: move, isSampleData: isSampleData, scrollToSources: atSources, onTestIt: { id in
                present(.testIt(moveID: id))
            }, onClose: close)
        case .plan:
            PlanScreen(client: client, onClose: close)
        case .accuracy:
            SpendAccuracyScreen(client: client, onClose: close)
        case .guess:
            GuessSpendView(state: model.guess.state, actions: model.guess.actions, onClose: close)
        }
    }
}

/// The one place that builds W7's "Test it" screen (ADR 0018). W7 owns `Features/TestIt`.
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
