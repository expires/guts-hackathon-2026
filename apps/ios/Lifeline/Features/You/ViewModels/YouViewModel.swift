import Foundation
import Observation

/// Loads `GET /v1/finance/profile` for the You tab and routes to settings screens.
@MainActor
@Observable
final class YouViewModel {
    enum Route: Equatable {
        case bank, plan, sources, evaluation, spendAccuracy, debug, connectMoney, askPenny, aiDisclosure, newPlayer, resetDemo, account, changeLanguage
    }

    static var loadingMessage: String { L10n.tr("Loading your profile") }

    private let client: any LifelineClient
    private(set) var profile: FinanceProfile?
    private(set) var lives: [LifeListItem] = []
    private(set) var conceptsTotal = 0
    private(set) var sources: [SourceStatus] = []
    /// `GET /v1/me`. Nil until loaded.
    private(set) var me: Me?
    private(set) var meFailed = false
    /// Backtest cases from `GET /v1/evaluation`. Nil until loaded.
    private(set) var evaluationCount: Int?
    /// `GET /v1/habits` (cached). Nil until loaded.
    private(set) var habitScore: HabitScore?
    /// Concepts unlocked in the running life. The glue sets it from `GameSession`.
    var conceptsUnlocked: Int?
    private let credits = CreditsFile.load()
    private(set) var phase: LoadPhase = .loading(.init(message: YouViewModel.loadingMessage))
    @ObservationIgnored var onRoute: @MainActor (Route) -> Void = { _ in }

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: YouViewState {
        Self.makeState(
            profile: profile, phase: phase, clientKind: client.kind, isDebugBuild: ClientFactory.isDebugBuild,
            lives: lives, conceptsUnlocked: conceptsUnlocked, conceptsTotal: conceptsTotal, sources: sources, credits: credits,
            connectMoneyText: Self.connectMoneyText(inputs: me?.financeInputs.map(\.rawValue), failed: meFailed),
            evaluationCount: evaluationCount,
            habits: habitScore
        )
    }

    /// Built by assignment, so a new closure never depends on the memberwise argument order.
    var actions: YouActions {
        var actions = YouActions()
        actions.onConnectMoney = { [weak self] in self?.onRoute(.connectMoney) }
        actions.onOpenAccount = { [weak self] in self?.onRoute(.account) }
        actions.onAskPenny = { [weak self] in self?.onRoute(.askPenny) }
        actions.onNewPlayer = { [weak self] in self?.onRoute(.newPlayer) }
        actions.onResetDemo = { [weak self] in self?.onRoute(.resetDemo) }
        actions.onOpenAIDisclosure = { [weak self] in self?.onRoute(.aiDisclosure) }
        actions.onChangeLanguage = { [weak self] in self?.onRoute(.changeLanguage) }
        actions.onRefresh = { [weak self] in await self?.load() }
        actions.onConnectBank = { [weak self] in self?.onRoute(.bank) }
        actions.onOpenPlan = { [weak self] in self?.onRoute(.plan) }
        actions.onOpenSources = { [weak self] in self?.onRoute(.sources) }
        actions.onOpenEvaluation = { [weak self] in self?.onRoute(.evaluation) }
        actions.onOpenSpendAccuracy = { [weak self] in self?.onRoute(.spendAccuracy) }
        actions.onOpenDebug = { [weak self] in
                if ClientFactory.isDebugBuild { self?.onRoute(.debug) }
            }
        actions.onRetry = { [weak self] in Task { await self?.load() } }
        return actions
    }

    /// Instant screen (ADR 0060): cached values show at once, the network copy replaces them quietly.
    /// A skeleton shows only when there is no cached profile yet.
    func load() async {
        if profile == nil { phase = .loading(.init(message: Self.loadingMessage)) }
        let client = self.client
        async let lives = client.listLives()
        async let evaluation = client.evaluation()
        async let meLoad: Void = client.load(CachedOps.me) { [weak self] value in
            self?.me = value
            self?.meFailed = false
        }
        async let conceptsLoad: Void = client.load(CachedOps.concepts) { [weak self] value in self?.conceptsTotal = value.count }
        async let sourcesLoad: Void = client.load(CachedOps.sources) { [weak self] value in self?.sources = value }
        async let habitsLoad: Void = client.load(CachedOps.habits) { [weak self] value in self?.habitScore = value }
        do {
            try await client.load(CachedOps.financeProfile) { [weak self] value in
                self?.profile = value
                self?.phase = .ready
            }
            phase = .ready
        } catch {
            // Keep cached content on a failed refresh; show the calm error only with nothing to show.
            if profile == nil { phase = .failed(Self.calmError(APIError.map(error))) }
        }
        do { try await meLoad } catch { meFailed = me == nil }
        _ = try? await conceptsLoad
        _ = try? await sourcesLoad
        _ = try? await habitsLoad
        if let value = try? await lives { self.lives = value.lives }
        if let value = try? await evaluation { evaluationCount = value.n }
    }

    /// Calm error for the You tab. Never shows rate-limit or server wording.
    static func calmError(_ error: APIError) -> ErrorViewState {
        let mapped = ErrorViewState.from(error)
        if mapped.isUnavailable { return mapped }
        return ErrorViewState(title: L10n.tr("Couldn't load"), message: L10n.tr("Pull to refresh."), canRetry: true)
    }

    static var versionText: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = info?["CFBundleVersion"] as? String ?? "1"
        return "\(version) (\(build))"
    }

    // MARK: Mapping (pure, used by fixtures and tests)

    static func makeState(
        profile: FinanceProfile?,
        phase: LoadPhase,
        clientKind: ClientKind,
        isDebugBuild: Bool,
        lives: [LifeListItem] = [],
        conceptsUnlocked: Int? = nil,
        conceptsTotal: Int = 0,
        sources: [SourceStatus] = [],
        credits: CreditsFile? = nil,
        connectMoneyText: String? = nil,
        evaluationCount: Int? = nil,
        habits: HabitScore? = nil,
        buildInfo: YouBuildInfo = .current()
    ) -> YouViewState {
        let isSample = profile.map { FinanceMapping.isSample($0.meta) } ?? (clientKind == .mock)
        let mapped = profile.map(Self.profile)
        let best = lives.map(\.index).max()
        let unlocked = conceptsUnlocked ?? 0
        var state = YouViewState(
            profilePhase: phase,
            profile: profile.map(Self.profile),
            personalFacts: profile?.personalFacts.map(\.text) ?? [],
            bankText: isSample
                ? L10n.tr("Not connected. The Money tab shows sample data.")
                : L10n.tr("Connected. The Money tab uses your bank data."),
            clientText: clientKind.rawValue,
            versionText: versionText,
            showsDebugMenu: isDebugBuild,
            isSampleData: isSample
        )
        if let mapped {
            state.personaLine = mapped.detail
        }
        state.bestIndexText = best.map { "\(Int($0.rounded()))" } ?? "-"
        state.ribbonsText = "\(lives.reduce(0) { $0 + $1.ribbons })"
        state.conceptsText = conceptsTotal > 0 ? "\(unlocked)/\(conceptsTotal)" : "\(unlocked)"
        state.bankName = isSample ? "Demo Bank" : "Your bank"
        state.bankDetail = isSample ? "Fake accounts, not your bank" : "Connected"
        state.dataRows = sources.filter { !isCutSource($0) }.map(dataRow)
        state.dataBadgeText = profile.flatMap { FinanceMapping.badgeText($0.meta) } ?? (profile == nil && clientKind == .mock ? L10n.tr("Mock data") : nil)
        state.showsEvaluation = (evaluationCount ?? 0) > 0
        state.habits = habits.flatMap(habitCard)
        state.credits = creditLines(credits)
        state.buildInfo = buildInfo
        state.connectMoneyText = connectMoneyText
        return state
    }

    static var connectMoneyError: String { L10n.tr("Couldn't load. Pull to refresh.") }

    /// `Me.finance_inputs` to one calm line. No bank connections in V2 (ADR 0046): a statement wins over
    /// manual entry. Nil inputs: still loading (nil) or failed (the calm error, never the raw API message).
    static func connectMoneyText(inputs: [String]?, failed: Bool) -> String? {
        guard let inputs else { return failed ? connectMoneyError : nil }
        if inputs.contains("sample") { return L10n.tr("Sample statement") }
        if inputs.contains("statement") { return L10n.tr("Statement imported") }
        if inputs.contains("manual") { return L10n.tr("Entered by hand") }
        if !inputs.isEmpty { return L10n.tr("Money added") }
        return L10n.tr("Not added yet")
    }

    /// Onboarding's words for housing (DIRECTION_V2 section 4).
    static func housingLabel(_ raw: String) -> String {
        switch raw {
        case "rent": L10n.tr("Renting")
        case "parents": L10n.tr("Lives with family")
        case "own": L10n.tr("Owns a home")
        case "mortgage": L10n.tr("Has a mortgage")
        default: raw.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    /// "Age 20 · Student · Renting": the three things onboarding asks (bug 7, ADR 0053).
    /// `isStudent` from onboarding wins; the occupation text is the fallback when it is nil.
    static func profileLine(age: Int, isStudent: Bool? = nil, occupation: String, housing: String) -> String {
        let student = isStudent ?? occupation.lowercased().contains("student")
        let work = student ? L10n.tr("Student") : L10n.tr("Working")
        return [L10n.tr("Age \(age)"), work, housingLabel(housing)].joined(separator: " · ")
    }

    /// Plain names for the six habit ratios, in display order (ADR 0066).
    static var habitNames: [(id: String, name: String)] { [
        ("savings_rate", L10n.tr("Savings rate")), ("months_of_cover", L10n.tr("Months of cover")), ("spend_stability", L10n.tr("Spend stability")),
        ("discretionary_share", L10n.tr("Discretionary share")), ("subscription_creep", L10n.tr("Subscription creep")), ("debt_pressure", L10n.tr("Debt pressure")),
    ] }

    /// Ratios present in the response, in a fixed order. Nil when there is nothing to show.
    static func habitCard(_ score: HabitScore) -> HabitCard? {
        let c = score.components
        let values: [String: Int?] = [
            "savings_rate": c.savingsRate, "months_of_cover": c.monthsOfCover, "spend_stability": c.spendStability,
            "discretionary_share": c.discretionaryShare, "subscription_creep": c.subscriptionCreep, "debt_pressure": c.debtPressure,
        ]
        let rows = habitNames.compactMap { item -> HabitCard.Row? in
            guard let value = values[item.id] ?? nil else { return nil }
            return .init(id: item.id, name: item.name, value: min(100, max(0, value)))
        }
        guard !rows.isEmpty || score.overall != nil else { return nil }
        return HabitCard(overall: score.overall, rows: rows)
    }

    /// Sources cut in V2 (no bank connections, no investments, no jobs or car data). W1 removes them
    /// server-side; until then the list hides them.
    static let cutSourceTokens = ["truelayer", "openbanking", "open banking", "monzo", "trading212", "trading 212", "adzuna", "dvla", "dvsa"]

    static func isCutSource(_ source: SourceStatus) -> Bool {
        let text = (source.id + " " + source.name).lowercased()
        return cutSourceTokens.contains { text.contains($0) }
    }

    static func dataRow(_ source: SourceStatus) -> YouViewState.DataRow {
        let status = StateMapping.status(source.status.rawValue)
        let detail: String = switch status {
        case .live: L10n.tr("Live")
        case .cached: L10n.tr("Saved copy")
        case .mock: L10n.tr("Mock data")
        case .unavailable: L10n.tr("Unavailable")
        }
        return .init(id: source.id, name: source.name, status: status, detail: detail)
    }

    /// Credits sentence plus one line per font licence. Empty when the file is missing.
    static func creditLines(_ credits: CreditsFile?) -> [String] {
        guard let credits else { return [] }
        return [L10n.tr("Credits: rates from the Bank of England. Icons, characters and design by the \(Brand.productName) team. Made in 24 hours at \(credits.event).")]
            + credits.fonts.map { "\($0.name) by \($0.authors). \($0.licence)." }
    }

    static func profile(_ profile: FinanceProfile) -> YouViewState.Profile {
        let character = profile.character
        let decision = profile.profile
        let housing = housingLabel(decision.housing.rawValue)
        return .init(
            emoji: character.emoji ?? "🙂",
            name: character.name,
            detail: profileLine(age: decision.age, isStudent: profile.isStudent, occupation: character.occupation, housing: decision.housing.rawValue),
            annualIncome: decision.annualIncome,
            savings: decision.savings,
            housingText: housing
        )
    }
}
