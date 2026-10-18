import Foundation
import Observation

/// Everything the Money tab shows: Next Move card first, then the widgets and "Guess my spend".
struct MoneyHomeViewState: Equatable, Sendable {
    struct Header: Equatable, Sendable {
        /// "Morning, Priya" or "Morning" when the profile has no first name. Follows local time (ADR 0070).
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

    /// "In your account" and "Net worth" for the compact line, from `GET /v1/finance/home`.
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

    /// True when the money blocks and Guess my spend show (data exists and loaded).
    var showsMoney: Bool { content == .ready }

    /// One block on Money home (ADR 0070).
    enum Block: String, Equatable, Sendable {
        case nextMove, weeklyBudget, spending, bills, subscriptions, budgetsAndGoals, accountLine, guess
    }

    /// Money home blocks, top to bottom (ADR 0070). Empty unless the money loaded.
    /// Each widget block shows its own skeleton, error or empty text, so only optional blocks drop out.
    var blocks: [Block] {
        guard showsMoney else { return [] }
        var blocks: [Block] = [.nextMove]
        if weeklyBudget != nil { blocks.append(.weeklyBudget) }
        blocks += [.spending, .bills, .subscriptions, .budgetsAndGoals]
        if tiles != nil { blocks.append(.accountLine) }
        blocks.append(.guess)
        return blocks
    }

    /// "In your account £1,186 · Net worth £2,040". Nil without both numbers.
    var accountLineText: String? {
        tiles.map { L10n.tr("In your account \(Money.format($0.balance)) · Net worth \(Money.format($0.netWorth))") }
    }

    /// At most 4 spending categories, largest first. £0 categories are already filtered out.
    var topCategories: [MoneyWidgetsViewState.Category] {
        Array((widgets.spending.value?.categories ?? []).sorted { $0.amount > $1.amount }.prefix(4))
    }

    /// At most 3 bills: from `/v1/finance/bills` once loaded (with price rise chips), else from home.
    var billsShown: [MoneyWidgetsViewState.Bill] {
        if let bills = widgets.bills.value { return Array(bills.items.prefix(3)) }
        return comingUp
    }
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
    /// Injected clock and calendar, so tests can fix the greeting's local hour.
    private let now: @Sendable () -> Date
    private let calendar: Calendar
    private(set) var profile: FinanceProfile?
    private(set) var home: FinanceHome?
    private(set) var homePhase: LoadPhase = .loading(.standard)
    /// The Next Move from `GET /v1/next-move?language=` in a non-English app language, with its language.
    /// `/v1/finance/home` sends move text in English only; numbers are the same in every language.
    private var localizedMove: (language: AppLanguage, response: NextMoveResponse)?
    private var hasLoaded = false
    /// Set when the user leaves to connect their money. The glue reloads on the next appearance.
    private(set) var needsReload = false
    @ObservationIgnored var onOpenGuess: @MainActor () -> Void = {}
    @ObservationIgnored var onOpenDetail: @MainActor (MoneyDetail) -> Void = { _ in }
    @ObservationIgnored var onConnectMoney: @MainActor () -> Void = {}
    @ObservationIgnored var onAskPenny: @MainActor (String?) -> Void = { _ in }

    static var connectPrompt: String { L10n.tr("Connect your money to see your next move") }

    init(client: any LifelineClient, now: @escaping @Sendable () -> Date = { Date() }, calendar: Calendar = .current) {
        self.client = client
        self.now = now
        self.calendar = calendar
        nextMove = NextMoveViewModel(client: client)
        widgets = MoneyWidgetsViewModel(client: client)
        guess = GuessSpendViewModel(client: client)
        let show: @MainActor (String) -> Void = { [weak nextMove] id in nextMove?.focus(id) }
        widgets.onShowMove = show
        guess.onShowMove = show
    }

    var state: MoneyHomeViewState {
        var state = MoneyHomeViewState(
            header: Self.header(profile: profile, now: now(), calendar: calendar),
            paydayText: guess.prediction?.daysToPayday.map(Self.paydayText),
            nextMove: nextMove.state,
            widgets: widgets.state,
            guess: guess.state
        )
        state.content = Self.content(phase: homePhase, home: home)
        if let home, home.hasData {
            // Both numbers or neither: never one of the two from another source.
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
        // The blocks under the Next Move (ADR 0070) load in parallel. Each shows from disk first.
        async let widgetsLoad: Void = self.widgets.load()
        await loadMoveIfNeeded()
        await nextMove.loadPlan()
        try? await client.load(CachedOps.financeProfile) { [weak self] profile in self?.profile = profile }
        await widgetsLoad
    }

    /// Shows a home value (from disk or the network) at once.
    func apply(_ loaded: FinanceHome) {
        home = loaded
        homePhase = .ready
        guard loaded.hasData else { return }
        guess.apply(prediction: loaded.prediction)
        let language = AppLanguage.current
        let separate = localizedMove.flatMap { $0.language == language ? $0.response : nil }
        // English: home's own move is the freshest. Other languages: the move text in that language.
        if let move = language == .en ? (loaded.nextMove ?? separate) : (separate ?? loaded.nextMove) {
            showMove(move)
        } else if nextMove.moves.isEmpty {
            // A slow server leaves `next_move` out of home. Keep the skeleton; `loadMoveIfNeeded` fetches it.
            nextMove.showLoading()
        }
    }

    private func showMove(_ response: NextMoveResponse?) {
        nextMove.show(response)
        widgets.moves = nextMove.moves
        guess.moves = nextMove.moves
    }

    /// Loads `GET /v1/next-move` (in the app language) when home cannot give the move as is:
    /// - a non-English app language: home sends move text in English only;
    /// - home came without `next_move` (slow server).
    /// From disk at once, then fresh. Runs on every load, so a language change reloads it.
    /// The card shows "No move right now" only when this call also gives no move; an error shows Try again.
    func loadMoveIfNeeded() async {
        let language = AppLanguage.current
        guard language != .en || home?.nextMove == nil else {
            localizedMove = nil
            return
        }
        do {
            try await client.load(Self.nextMoveOp(language)) { [weak self] response in
                guard let self, AppLanguage.current == language else { return }
                localizedMove = (language, response)
                showMove(response)
            }
        } catch {
            if nextMove.moves.isEmpty { nextMove.showFailure(APIError.map(error)) }
        }
    }

    /// One disk cache file per language, so each language shows its own text at once.
    static func nextMoveOp(_ language: AppLanguage) -> CachedOp<NextMoveResponse> {
        CachedOp(key: "getNextMove." + language.rawValue, scope: .user) { try await $0.nextMove() }
    }

    /// The weekly budget block from the engine's weekly_budget move (top or runner-up). Nil without
    /// a safe weekly spend: never an invented number.
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

    /// Part of the day for the greeting, by local hour (ADR 0070).
    enum DayPart: Equatable, Sendable {
        /// 05:00 to 11:59.
        case morning
        /// 12:00 to 17:59.
        case afternoon
        /// 18:00 to 22:59.
        case evening
        /// 23:00 to 04:59: "Hi".
        case lateNight

        init(hour: Int) {
            switch hour {
            case 5..<12: self = .morning
            case 12..<18: self = .afternoon
            case 18..<23: self = .evening
            default: self = .lateNight
            }
        }
    }

    /// "Morning", or "Morning, Priya" with a first name. Translated (ADR 0063).
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

    /// "Morning, Priya" by the phone's local time. The name "You" (no real name) gives just "Morning".
    static func header(profile: FinanceProfile?, now: Date, calendar: Calendar = .current) -> MoneyHomeViewState.Header {
        let part = DayPart(hour: calendar.component(.hour, from: now))
        let name = profile?.character.name.split(separator: " ").first.map(String.init)
        return .init(greeting: greeting(part, name: name == "You" ? nil : name), faceEmoji: profile?.character.emoji ?? "🙂")
    }

    /// "Payday in 27 days", "Payday tomorrow", "Payday today".
    static func paydayText(_ days: Int) -> String {
        switch days {
        case ..<1: "Payday today"
        case 1: "Payday tomorrow"
        default: L10n.tr("Payday in \(days) days")
        }
    }
}
