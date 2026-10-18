import Foundation
import Observation

/// Everything Money home shows (ADR 0072, B3): the forecast card, where your money goes, the bills due
/// before the next money, one thing that helps, and one line "In your account £X".
struct MoneyHomeViewState: Equatable, Sendable {
    struct Header: Equatable, Sendable {
        /// "Hi, Eilidh", or "Hi" when the profile has no first name. Same at every time of day (G1).
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

    /// Older home numbers. Kept for the older fixtures; Money home no longer shows them (B4).
    struct Tiles: Equatable, Sendable {
        var balance: Double
        var netWorth: Double
    }

    var header: Header = .init(greeting: "Hi", faceEmoji: "🙂")
    var content: Content = .ready
    var tiles: Tiles?
    var comingUp: [MoneyWidgetsViewState.Bill] = []
    var comingUpMore = false
    var homeIsSampleData = false
    var badgeText: String?
    var weeklyBudget: WeeklyBudget?

    struct WeeklyBudget: Equatable, Sendable {
        var moveID: String
        var text: String
        var detail: String?
    }

    var paydayText: String? = nil
    /// The old Next Move, widgets and Guess my spend. Not shown on Money home (B4); kept so older code compiles.
    var nextMove: NextMoveCardState
    var widgets: MoneyWidgetsViewState
    var guess: GuessSpendViewState

    // MARK: Forecast (ADR 0072)

    /// The forecast card: loading skeleton, a calm error, or the card.
    var forecastPhase: LoadPhase = .loading(.standard)
    var forecast: ForecastCardState?
    /// "Where your money goes": this month so far.
    var spendingPhase: LoadPhase = .loading(.standard)
    var spending: SpendingPieState?
    /// "Due before 2 November".
    var due: ForecastDueState?
    /// "One thing that helps".
    var help: ForecastHelpState?
    /// Money now from the forecast (current accounts), for "In your account £318".
    var moneyNow: Double?
    /// "Your habits": shown right after the forecast card. Not part of `blocks`.
    var habits: HabitsPanelState = .loading

    /// Kept for older call sites. Money home never shows a "Mock data" or "Sample data" tag (B4).
    var isSampleData: Bool { false }

    /// True when the money blocks show (data exists and loaded).
    var showsMoney: Bool { content == .ready }

    /// One block on Money home, top to bottom.
    enum Block: String, Equatable, Sendable {
        case forecast, spending, due, help, accountLine
    }

    /// Money home blocks (B3.1, B3.2). Empty unless the money loaded. Due, help and the account line drop out
    /// when the forecast has none.
    var blocks: [Block] {
        guard showsMoney else { return [] }
        var blocks: [Block] = [.forecast, .spending]
        if due != nil { blocks.append(.due) }
        if help != nil { blocks.append(.help) }
        if moneyNow != nil { blocks.append(.accountLine) }
        return blocks
    }

    /// "In your account £318". The forecast's money now, rounded like the card.
    var accountLineText: String? {
        moneyNow.map { L10n.tr("In your account \(Money.format($0))") }
    }
}

/// Money detail screens of the older "Your money" view. Kept for `MoneyDetailsView`; not reachable from Money home.
enum MoneyDetail: String, Hashable, Sendable, Identifiable {
    case accounts
    case netWorth
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
    var onRefresh: @MainActor () async -> Void = {}
    /// "Connect your money": opens onboarding at the connect step.
    var onConnectMoney: @MainActor () -> Void = {}
    /// Header button: Ask Penny about Money.
    var onAskPenny: @MainActor () -> Void = {}
    /// Forecast card: "See the maths".
    var onSeeMaths: @MainActor () -> Void = {}
    /// Forecast card: "Ask Penny" (forecast loaded, "Explain my weekly budget").
    var onAskPennyForecast: @MainActor () -> Void = {}
    /// "See all spending".
    var onSeeAllSpending: @MainActor () -> Void = {}
    /// A category row in "Where your money goes".
    var onCategory: @MainActor (_ id: String, _ label: String) -> Void = { _, _ in }
    var onRetryForecast: @MainActor () -> Void = {}
    var onRetrySpending: @MainActor () -> Void = {}
    /// "Your habits" card: opens the profile stats page.
    var onOpenHabits: @MainActor () -> Void = {}
    /// "Your habits" empty state: opens the connections editor.
    var onConnectHabits: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// Money tab coordinator (ADR 0072). Loads home (has data or not), then the forecast, this month's spending
/// and the profile in parallel. Each shows from disk first (ADR 0060).
@MainActor
@Observable
final class MoneyHomeViewModel {
    /// Older parts, kept so their screens and tests still build. Money home does not load them.
    let nextMove: NextMoveViewModel
    let widgets: MoneyWidgetsViewModel
    let guess: GuessSpendViewModel
    private let client: any LifelineClient
    private let now: @Sendable () -> Date
    private let calendar: Calendar
    private(set) var profile: FinanceProfile?
    private(set) var home: FinanceHome?
    private(set) var homePhase: LoadPhase = .loading(.standard)
    private(set) var forecast: Forecast?
    private var forecastPhase: LoadPhase = .loading(.standard)
    private(set) var spending: SpendingResponse?
    private var spendingPhase: LoadPhase = .loading(.standard)
    private var habits: HabitsPanelState = .loading
    private var hasLoaded = false
    /// Set when the user leaves to connect their money. The glue reloads on the next appearance.
    private(set) var needsReload = false
    @ObservationIgnored var onConnectMoney: @MainActor () -> Void = {}
    @ObservationIgnored var onAskPenny: @MainActor () -> Void = {}
    @ObservationIgnored var onAskPennyForecast: @MainActor () -> Void = {}
    @ObservationIgnored var onSeeMaths: @MainActor () -> Void = {}
    @ObservationIgnored var onSeeAllSpending: @MainActor () -> Void = {}
    @ObservationIgnored var onCategory: @MainActor (String, String) -> Void = { _, _ in }
    @ObservationIgnored var onOpenHabits: @MainActor () -> Void = {}
    @ObservationIgnored var onConnectHabits: @MainActor () -> Void = {}

    static var connectPrompt: String { L10n.tr("Connect your money to see your next move") }

    init(client: any LifelineClient, now: @escaping @Sendable () -> Date = { Date() }, calendar: Calendar = .current) {
        self.client = client
        self.now = now
        self.calendar = calendar
        nextMove = NextMoveViewModel(client: client)
        widgets = MoneyWidgetsViewModel(client: client)
        guess = GuessSpendViewModel(client: client)
    }

    var state: MoneyHomeViewState {
        var state = MoneyHomeViewState(
            header: Self.header(profile: profile, now: now(), calendar: calendar),
            nextMove: nextMove.state,
            widgets: widgets.state,
            guess: guess.state
        )
        state.content = Self.content(phase: homePhase, home: home)
        state.forecastPhase = forecast == nil ? forecastPhase : .ready
        state.spendingPhase = spending == nil ? spendingPhase : .ready
        if let forecast {
            state.forecast = ForecastCardState.make(forecast)
            state.due = ForecastDueState.make(forecast)
            state.help = ForecastHelpState.make(forecast)
            state.moneyNow = forecast.moneyNow
        }
        state.habits = habits
        state.spending = spending.map { SpendingPieState.make($0) }
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
            onRefresh: { [weak self] in await self?.refresh() },
            onConnectMoney: { [weak self] in
                self?.needsReload = true
                self?.onConnectMoney()
            },
            onAskPenny: { [weak self] in self?.onAskPenny() },
            onSeeMaths: { [weak self] in self?.onSeeMaths() },
            onAskPennyForecast: { [weak self] in self?.onAskPennyForecast() },
            onSeeAllSpending: { [weak self] in self?.onSeeAllSpending() },
            onCategory: { [weak self] id, label in self?.onCategory(id, label) },
            onRetryForecast: { [weak self] in Task { await self?.loadForecast() } },
            onRetrySpending: { [weak self] in Task { await self?.loadSpending() } },
            onOpenHabits: { [weak self] in self?.onOpenHabits() },
            onConnectHabits: { [weak self] in self?.onConnectHabits() }
        )
    }

    /// First appearance only. Pull to refresh calls `refresh()`.
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

    func load() async {
        hasLoaded = true
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
        async let forecastLoad: Void = loadForecast()
        async let spendingLoad: Void = loadSpending()
        async let habitsLoad: Void = loadHabits()
        try? await client.load(CachedOps.financeProfile) { [weak self] profile in self?.profile = profile }
        _ = await (forecastLoad, spendingLoad, habitsLoad)
    }

    /// Shows a home value (from disk or the network) at once.
    func apply(_ loaded: FinanceHome) {
        home = loaded
        homePhase = .ready
    }

    /// `GET /v1/forecast` in the app language, cached per language.
    func loadForecast() async {
        if forecast == nil { forecastPhase = .loading(.standard) }
        do {
            try await client.load(CachedOps.forecast) { [weak self] value in self?.show(value) }
        } catch {
            if forecast == nil { forecastPhase = .failed(.from(APIError.map(error))) }
        }
    }

    /// `GET /v1/habits`. No transactions (409) or any failure gives the empty state, never an error card.
    func loadHabits() async {
        if habits.phase != .score { habits = .loading }
        do {
            try await client.load(CachedOps.habits) { [weak self] score in
                guard let self else { return }
                habits = HabitsPanelState.make(score, meta: home?.meta)
            }
        } catch {
            if habits.phase != .score { habits = .empty }
        }
    }

    /// A new forecast, e.g. after the buffer changed on "The maths".
    func show(_ value: Forecast) {
        forecast = value
        forecastPhase = .ready
    }

    /// This month's spending for the pie.
    func loadSpending() async {
        if spending == nil { spendingPhase = .loading(.standard) }
        do {
            try await client.load(CachedOps.spending()) { [weak self] value in
                self?.spending = value
                self?.spendingPhase = .ready
            }
        } catch {
            if spending == nil { spendingPhase = .failed(.from(APIError.map(error))) }
        }
    }

    // MARK: Greeting

    /// Part of the day. Kept for older callers; the greeting no longer changes with the time (G1).
    enum DayPart: Equatable, Sendable {
        case morning, afternoon, evening, lateNight

        init(hour: Int) {
            switch hour {
            case 5..<12: self = .morning
            case 12..<18: self = .afternoon
            case 18..<23: self = .evening
            default: self = .lateNight
            }
        }
    }

    /// "Morning, Priya" by part of day. Kept for older callers; Money home uses `greeting(name:)`.
    static func greeting(_ part: DayPart, name: String?) -> String {
        guard let name, !name.isEmpty else {
            switch part {
            case .morning: return L10n.tr("Morning")
            case .afternoon: return L10n.tr("Afternoon")
            case .evening: return L10n.tr("Evening")
            case .lateNight: return L10n.tr("Hi")
            }
        }
        switch part {
        case .morning: return L10n.tr("Morning, \(name)")
        case .afternoon: return L10n.tr("Afternoon, \(name)")
        case .evening: return L10n.tr("Evening, \(name)")
        case .lateNight: return L10n.tr("Hi, \(name)")
        }
    }

    /// "Hi, Eilidh" or "Hi" (G1). Translated.
    static func greeting(name: String?) -> String {
        guard let name, !name.isEmpty else { return L10n.tr("Hi") }
        return L10n.tr("Hi, \(name)")
    }

    /// "Hi, Eilidh" at every time of day. The name "You" (no real name) gives just "Hi".
    static func header(profile: FinanceProfile?, now: Date, calendar: Calendar = .current) -> MoneyHomeViewState.Header {
        let name = profile?.character.name.split(separator: " ").first.map(String.init)
        return .init(greeting: greeting(name: name == "You" ? nil : name), faceEmoji: profile?.character.emoji ?? "🙂")
    }

    /// "Payday in 27 days", "Payday tomorrow", "Payday today". Kept for the older fixtures.
    static func paydayText(_ days: Int) -> String {
        switch days {
        case ..<1: L10n.tr("Payday today")
        case 1: L10n.tr("Payday tomorrow")
        default: L10n.tr("Payday in \(days) days")
        }
    }

    /// Kept for `WeeklyBudgetTests`: the older weekly budget block from a weekly_budget move.
    static func weeklyBudget(_ moves: [Move]) -> MoneyHomeViewState.WeeklyBudget? {
        guard let move = moves.first(where: { $0.kind.rawValue == "weekly_budget" }),
              let weekly = move.safeWeeklySpend else { return nil }
        let amount = Money.format(weekly.rounded())
        let text = move.deadline.map { deadline in
            let date = NextMoveViewModel.longDayText(deadline)
            return L10n.tr("Until \(date): spend up to \(amount) a week")
        } ?? L10n.tr("Until your next money: spend up to \(amount) a week")
        return .init(
            moveID: move.id,
            text: text,
            detail: move.coverWeeks.map { weeks in
                let count = NextMoveViewModel.weeksText(weeks)
                return L10n.tr("\(count) until your next money")
            }
        )
    }
}
