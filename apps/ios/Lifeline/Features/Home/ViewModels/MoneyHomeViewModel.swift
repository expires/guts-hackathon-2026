import Foundation
import Observation

/// Everything the Money tab shows: Next Move card first, then the widgets and "Guess my spend".
struct MoneyHomeViewState: Equatable, Sendable {
    struct Header: Equatable, Sendable {
        /// "Morning, Priya" or "Morning" when the profile has no first name.
        var greeting: String
        /// Character emoji from `/v1/finance/profile`. The View maps it to a face icon.
        var faceEmoji: String
    }

    var header: Header = .init(greeting: "Hello", faceEmoji: "🙂")
    /// "Payday in 27 days". From the spend prediction. Nil when unknown.
    var paydayText: String? = nil
    var nextMove: NextMoveCardState
    var widgets: MoneyWidgetsViewState
    var guess: GuessSpendViewState

    /// True when any part shows sample data.
    var isSampleData: Bool { nextMove.isSampleData || widgets.isSampleData || guess.isSampleData }
}

/// Money detail screens opened from the Money tab.
enum MoneyDetail: String, Hashable, Sendable, Identifiable {
    /// "In your account": balance and accounts.
    case accounts
    /// Net worth chart and accounts.
    case netWorth
    /// "See all": spending, bills, subscriptions, budgets, savings goals.
    case all

    var id: String { rawValue }

    var title: String {
        switch self {
        case .accounts: "In your account"
        case .netWorth: "Net worth"
        case .all: "Your money"
        }
    }
}

struct MoneyHomeActions {
    var nextMove: NextMoveActions = .noop
    var widgets: MoneyWidgetsActions = .noop
    var guess: GuessSpendActions = .noop
    var onRefresh: @MainActor () async -> Void = {}
    /// Opens the full "Guess my spend" screen.
    var onOpenGuess: @MainActor () -> Void = {}
    /// Opens a Money detail screen.
    var onOpenDetail: @MainActor (MoneyDetail) -> Void = { _ in }

    static var noop: Self { .init() }
}

/// Money tab coordinator. Owns the Next Move, widgets and guess ViewModels and links them (ADR 0018).
@MainActor
@Observable
final class MoneyHomeViewModel {
    let nextMove: NextMoveViewModel
    let widgets: MoneyWidgetsViewModel
    let guess: GuessSpendViewModel
    private let client: any LifelineClient
    private let now: @Sendable () -> Date
    private(set) var profile: FinanceProfile?
    private var hasLoaded = false
    @ObservationIgnored var onOpenGuess: @MainActor () -> Void = {}
    @ObservationIgnored var onOpenDetail: @MainActor (MoneyDetail) -> Void = { _ in }

    init(client: any LifelineClient, now: @escaping @Sendable () -> Date = { Date() }) {
        self.client = client
        self.now = now
        nextMove = NextMoveViewModel(client: client)
        widgets = MoneyWidgetsViewModel(client: client)
        guess = GuessSpendViewModel(client: client)
        let show: @MainActor (String) -> Void = { [weak nextMove] id in nextMove?.focus(id) }
        widgets.onShowMove = show
        guess.onShowMove = show
    }

    var state: MoneyHomeViewState {
        MoneyHomeViewState(
            header: Self.header(profile: profile, now: now()),
            paydayText: guess.prediction?.daysToPayday.map(Self.paydayText),
            nextMove: nextMove.state,
            widgets: widgets.state,
            guess: guess.state
        )
    }

    var actions: MoneyHomeActions {
        MoneyHomeActions(
            nextMove: nextMove.actions,
            widgets: widgets.actions,
            guess: guess.actions,
            onRefresh: { [weak self] in await self?.load() },
            onOpenGuess: { [weak self] in self?.onOpenGuess() },
            onOpenDetail: { [weak self] in self?.onOpenDetail($0) }
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
        profile = try? await client.financeProfile()
        await nextMove.load()
        widgets.moves = nextMove.moves
        guess.moves = nextMove.moves
        async let widgetsDone: Void = widgets.load()
        async let guessDone: Void = guess.load()
        _ = await (widgetsDone, guessDone)
    }

    /// "Morning, Priya". The name "You" (no real name) gives just "Morning".
    static func header(profile: FinanceProfile?, now: Date, calendar: Calendar = .init(identifier: .gregorian)) -> MoneyHomeViewState.Header {
        let hour = calendar.component(.hour, from: now)
        let part = hour < 12 ? "Morning" : (hour < 18 ? "Afternoon" : "Evening")
        let name = profile?.character.name.split(separator: " ").first.map(String.init)
        let greeting = (name == nil || name == "You") ? part : "\(part), \(name!)"
        return .init(greeting: greeting, faceEmoji: profile?.character.emoji ?? "🙂")
    }

    /// "Payday in 27 days", "Payday tomorrow", "Payday today".
    static func paydayText(_ days: Int) -> String {
        switch days {
        case ..<1: "Payday today"
        case 1: "Payday tomorrow"
        default: "Payday in \(days) days"
        }
    }
}
