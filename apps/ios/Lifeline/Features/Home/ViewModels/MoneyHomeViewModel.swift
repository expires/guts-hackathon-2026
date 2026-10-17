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

    /// What the screen body shows. At most one empty or error state.
    enum Content: Equatable, Sendable {
        case loading(LoadingViewState)
        /// `has_data` is false: one card, "Connect your money".
        case connect(prompt: String)
        case failed(ErrorViewState)
        case ready
    }

    /// "In your account" and "Net worth" tiles, from `GET /v1/finance/home`.
    struct Tiles: Equatable, Sendable {
        var balance: Double
        var netWorth: Double
    }

    var header: Header = .init(greeting: "Hello", faceEmoji: "🙂")
    var content: Content = .ready
    var tiles: Tiles?
    /// At most 3 bills.
    var comingUp: [MoneyWidgetsViewState.Bill] = []
    /// More bills than the 3 shown.
    var comingUpMore = false
    /// Data status from `FinanceHome.meta` is mock or sample.
    var homeIsSampleData = false
    /// "Sample data" or "Mock data" for the badge. Nil for the user's real data.
    var badgeText: String?
    /// "Until 2 November: spend up to £82 a week", from the weekly_budget move. Nil hides the block.
    var weeklyBudget: WeeklyBudget?

    struct WeeklyBudget: Equatable, Sendable {
        var moveID: String
        var text: String
        /// "3 weeks until your next money". Nil when cover_weeks is not sent.
        var detail: String?
    }
    /// "Payday in 27 days". From the spend prediction. Nil when unknown.
    var paydayText: String? = nil
    var nextMove: NextMoveCardState
    var widgets: MoneyWidgetsViewState
    var guess: GuessSpendViewState

    /// True when any part shows sample data.
    var isSampleData: Bool { homeIsSampleData || nextMove.isSampleData || guess.isSampleData }

    /// True when the tiles, Guess my spend and Coming up show (data exists and loaded).
    var showsMoney: Bool { content == .ready }
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
    /// "Connect your money": opens onboarding at the connect step.
    var onConnectMoney: @MainActor () -> Void = {}
    /// Opens Ask Penny about the Money tab or the Next Move.
    var onAskPenny: @MainActor (_ nextMoveID: String?) -> Void = { _ in }

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
    private(set) var home: FinanceHome?
    private(set) var homePhase: LoadPhase = .loading(.standard)
    private var hasLoaded = false
    /// Set when the user leaves to connect their money. The glue reloads on the next appearance.
    private(set) var needsReload = false
    @ObservationIgnored var onOpenGuess: @MainActor () -> Void = {}
    @ObservationIgnored var onOpenDetail: @MainActor (MoneyDetail) -> Void = { _ in }
    @ObservationIgnored var onConnectMoney: @MainActor () -> Void = {}
    @ObservationIgnored var onAskPenny: @MainActor (String?) -> Void = { _ in }

    static let connectPrompt = "Connect your money to see your next move"

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
        var state = MoneyHomeViewState(
            header: Self.header(profile: profile, now: now()),
            paydayText: guess.prediction?.daysToPayday.map(Self.paydayText),
            nextMove: nextMove.state,
            widgets: widgets.state,
            guess: guess.state
        )
        state.content = Self.content(phase: homePhase, home: home)
        if let home, home.hasData {
            state.tiles = home.balance.flatMap { balance in home.netWorth.map { .init(balance: balance, netWorth: $0) } }
            state.comingUp = (home.comingUp ?? []).prefix(3).map(MoneyWidgetsViewModel.bill)
            state.comingUpMore = home.comingUpMore ?? false
        }
        state.homeIsSampleData = home?.meta.map(FinanceMapping.isSample) ?? false
        state.badgeText = home?.meta.flatMap(FinanceMapping.badgeText)
        if home?.hasData == true { state.weeklyBudget = Self.weeklyBudget(nextMove.moves) }
        return state
    }

    /// The body state: loading, the one connect card, an error, or the money.
    static func content(phase: LoadPhase, home: FinanceHome?) -> MoneyHomeViewState.Content {
        switch phase {
        case let .loading(loading): return .loading(loading)
        case let .failed(error): return .failed(error)
        case .ready:
            guard let home, home.hasData else {
                let prompt = home?.connectPrompt.flatMap { $0.isEmpty ? nil : $0 } ?? connectPrompt
                return .connect(prompt: prompt)
            }
            return .ready
        }
    }

    var actions: MoneyHomeActions {
        MoneyHomeActions(
            nextMove: nextMove.actions,
            widgets: widgets.actions,
            guess: guess.actions,
            onRefresh: { [weak self] in await self?.refresh() },
            onOpenGuess: { [weak self] in
                guard let self else { return }
                Task { await self.guess.load() }
                onOpenGuess()
            },
            onOpenDetail: { [weak self] detail in
                guard let self else { return }
                Task { await self.widgets.loadIfNeeded() }
                onOpenDetail(detail)
            },
            onConnectMoney: { [weak self] in
                self?.needsReload = true
                self?.onConnectMoney()
            },
            onAskPenny: { [weak self] in self?.onAskPenny($0) }
        )
    }

    /// First appearance only. Pull to refresh calls `load()`.
    func loadIfNeeded() async {
        guard !hasLoaded else { return }
        hasLoaded = true
        await load()
    }

    /// Pull to refresh: drop the cached GETs first, so the numbers are fresh.
    func refresh() async {
        await client.clearResponseCache()
        await load()
    }

    /// Reloads after the user came back from connecting their money.
    func reloadIfNeeded() async {
        guard needsReload else { return }
        needsReload = false
        await load()
    }

    /// One request: `GET /v1/finance/home`. No data is a normal state, not an error.
    /// The plan (In plan marks) and the profile (the name in the greeting) load quietly afterwards.
    func load() async {
        // Skeletons only when nothing is known yet. A cached home shows at once (ADR 0060).
        if home == nil { homePhase = .loading(.standard) }
        do {
            try await client.load(CachedOps.financeHome) { [weak self] home in self?.apply(home) }
        } catch {
            if home == nil { homePhase = .failed(.from(APIError.map(error))) }
            return
        }
        guard home?.hasData == true else {
            profile = nil
            return
        }
        await nextMove.loadPlan()
        try? await client.load(CachedOps.financeProfile) { [weak self] profile in self?.profile = profile }
    }

    /// Shows a home value (from disk or the network) at once.
    func apply(_ loaded: FinanceHome) {
        home = loaded
        homePhase = .ready
        guard loaded.hasData else { return }
        guess.apply(prediction: loaded.prediction)
        nextMove.show(loaded.nextMove)
        widgets.moves = nextMove.moves
        guess.moves = nextMove.moves
    }

    /// The weekly budget block from the engine's weekly_budget move (top or runner-up). Nil without
    /// a safe weekly spend: never an invented number.
    static func weeklyBudget(_ moves: [Move]) -> MoneyHomeViewState.WeeklyBudget? {
        guard let move = moves.first(where: { $0.kind.rawValue == "weekly_budget" }),
              let weekly = move.safeWeeklySpend else { return nil }
        let until = move.deadline.map { "Until " + NextMoveViewModel.longDayText($0) } ?? "Until your next money"
        return .init(
            moveID: move.id,
            text: "\(until): spend up to \(Money.format(weekly.rounded())) a week",
            detail: move.coverWeeks.map { NextMoveViewModel.weeksText($0) + " until your next money" }
        )
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
