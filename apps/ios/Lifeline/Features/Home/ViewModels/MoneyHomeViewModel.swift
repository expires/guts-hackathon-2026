import Foundation
import Observation

/// Everything the Money tab shows: Next Move card first, then the widgets and "Guess my spend".
struct MoneyHomeViewState: Equatable, Sendable {
    var nextMove: NextMoveCardState
    var widgets: MoneyWidgetsViewState
    var guess: GuessSpendViewState

    /// True when any part shows sample data.
    var isSampleData: Bool { nextMove.isSampleData || widgets.isSampleData || guess.isSampleData }
}

struct MoneyHomeActions {
    var nextMove: NextMoveActions = .noop
    var widgets: MoneyWidgetsActions = .noop
    var guess: GuessSpendActions = .noop
    var onRefresh: @MainActor () async -> Void = {}

    static var noop: Self { .init() }
}

/// Money tab coordinator. Owns the Next Move, widgets and guess ViewModels and links them (ADR 0018).
@MainActor
@Observable
final class MoneyHomeViewModel {
    let nextMove: NextMoveViewModel
    let widgets: MoneyWidgetsViewModel
    let guess: GuessSpendViewModel
    private var hasLoaded = false

    init(client: any LifelineClient) {
        nextMove = NextMoveViewModel(client: client)
        widgets = MoneyWidgetsViewModel(client: client)
        guess = GuessSpendViewModel(client: client)
        let show: @MainActor (String) -> Void = { [weak nextMove] id in nextMove?.focus(id) }
        widgets.onShowMove = show
        guess.onShowMove = show
    }

    var state: MoneyHomeViewState {
        MoneyHomeViewState(nextMove: nextMove.state, widgets: widgets.state, guess: guess.state)
    }

    var actions: MoneyHomeActions {
        MoneyHomeActions(
            nextMove: nextMove.actions,
            widgets: widgets.actions,
            guess: guess.actions,
            onRefresh: { [weak self] in await self?.load() }
        )
    }

    /// First appearance only. Pull to refresh calls `load()`.
    func loadIfNeeded() async {
        guard !hasLoaded else { return }
        hasLoaded = true
        await load()
    }

    /// The Next Move loads first (top priority), then the rest in parallel.
    func load() async {
        await nextMove.load()
        widgets.moves = nextMove.moves
        guess.moves = nextMove.moves
        async let widgetsDone: Void = widgets.load()
        async let guessDone: Void = guess.load()
        _ = await (widgetsDone, guessDone)
    }
}
