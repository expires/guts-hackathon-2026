import Foundation
import Observation

/// Loads `GET /v1/finance/profile` for the You tab and routes to settings screens.
@MainActor
@Observable
final class YouViewModel {
    enum Route: Equatable {
        case bank, plan, sources, evaluation, spendAccuracy, debug, connectMoney, askPenny, aiDisclosure, newPlayer, resetDemo, account, changeLanguage, learn
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
    /// Learn progress (done, total). The glue sets it from the Learn path.
    var lessons: (done: Int, total: Int)?
    /// The stored safety buffer % from `GET /v1/forecast`. Nil until loaded or without a forecast.
    private(set) var bufferPct: Int?
    private(set) var isSavingBuffer = false
    private(set) var bufferError: String?
    @ObservationIgnored private var bufferGeneration = 0
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
            habits: habitScore,
            displayName: me?.displayName,
            lessons: lessons,
            buffer: bufferPct.map { .init(selected: $0, isSaving: isSavingBuffer, errorText: bufferError) },
            showsCutFeatures: FeatureFlags.showsCutFeatures
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
        actions.onOpenLearn = { [weak self] in self?.onRoute(.learn) }
        actions.onSetBuffer = { [weak self] pct in Task { await self?.setBuffer(pct) } }
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
        async let forecastLoad: Void = client.load(CachedOps.forecast) { [weak self] value in
            guard let self, !self.isSavingBuffer else { return }
            self.bufferPct = value.bufferPct.rawValue
        }
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
        _ = try? await forecastLoad
        if let value = try? await lives { self.lives = value.lives }
        if let value = try? await evaluation { evaluationCount = value.n }
    }

    nonisolated static let bufferOptions = [0, 5, 10, 15, 20]

    /// "Safety buffer" (PENNY_V3_BUILD B2): shows the new value at once, stores it, then refreshes the cached
    /// forecast so Money home uses it. A failed save goes back to the stored value.
    func setBuffer(_ pct: Int) async {
        guard Self.bufferOptions.contains(pct), pct != bufferPct else { return }
        let previous = bufferPct
        bufferGeneration += 1
        let generation = bufferGeneration
        bufferPct = pct
        bufferError = nil
        isSavingBuffer = true
        defer { if generation == bufferGeneration { isSavingBuffer = false } }
        do {
            _ = try await client.setForecastSettings(bufferPct: pct)
            guard generation == bufferGeneration else { return }
            await client.refresh(CachedOps.forecast)
        } catch {
            guard generation == bufferGeneration else { return }
            bufferPct = previous
            bufferError = L10n.tr("Couldn't save your buffer. Try again.")
        }
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
        displayName: String? = nil,
        lessons: (done: Int, total: Int)? = nil,
        buffer: YouViewState.BufferSetting? = nil,
        showsCutFeatures: Bool = false,
        buildInfo: YouBuildInfo = .current()
    ) -> YouViewState {
        let isSample = profile.map { FinanceMapping.isSample($0.meta) } ?? (clientKind == .mock)
        let mapped = profile.map { Self.profile($0, displayName: displayName) }
        let best = lives.map(\.index).max()
        let unlocked = conceptsUnlocked ?? 0
        var state = YouViewState(
            profilePhase: phase,
            profile: mapped,
            personalFacts: profile?.personalFacts.map(\.text) ?? [],
            bankText: isSample
                ? L10n.tr("Not connected. The Money tab shows a sample statement.")
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
        state.lessonsText = lessonsText(lessons)
        state.honestyText = honestyLine
        state.buffer = buffer
        state.showsCutFeatures = showsCutFeatures
        state.bankName = isSample ? "Demo Bank" : "Your bank"
        state.bankDetail = isSample ? "Fake accounts, not your bank" : "Connected"
        state.dataRows = dataRows(sources)
        // No "Mock data" or "Sample data" tags (PENNY_V3_BUILD B4): the honesty line says it once.
        state.dataBadgeText = nil
        state.showsEvaluation = showsCutFeatures && (evaluationCount ?? 0) > 0
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

    /// Plain names for the six habit ratios, in display order (ADR 0066). One set of names everywhere
    /// (PENNY_V3_BUILD C7): the profile in onboarding uses the same words.
    static var habitNames: [(id: String, name: String)] { [
        ("savings_rate", L10n.tr("Saving")), ("months_of_cover", L10n.tr("Safety cushion")), ("spend_stability", L10n.tr("Steady spending")),
        ("discretionary_share", L10n.tr("Needs before wants")), ("subscription_creep", L10n.tr("Subscriptions in check")), ("debt_pressure", L10n.tr("Low debt pressure")),
    ] }

    /// "3/48" for the Lessons tile. "-" before the path loads.
    static func lessonsText(_ lessons: (done: Int, total: Int)?) -> String {
        guard let lessons, lessons.total > 0 else { return "-" }
        return "\(lessons.done)/\(lessons.total)"
    }

    /// The one honesty line (PENNY_V3_BUILD B4), on "Pick your student" and here.
    static var honestyLine: String {
        L10n.tr("These are sample students. UK banks do not give apps like ours access to real accounts without a licence, so Penny runs on sample statements built from real UK figures.")
    }

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

    /// Sources cut in V2 (no bank connections, no investments, no jobs or car data). Kept for older callers.
    static let cutSourceTokens = ["truelayer", "openbanking", "open banking", "monzo", "trading212", "trading 212", "adzuna", "dvla", "dvsa"]

    static func isCutSource(_ source: SourceStatus) -> Bool {
        let text = (source.id + " " + source.name).lowercased()
        return cutSourceTokens.contains { text.contains($0) } || !studentSourceIDs.contains(source.id)
    }

    /// Student-facing sources, in display order (PENNY_V3_BUILD B4), with their plain names.
    static var studentSources: [(id: String, name: String)] { [
        ("boe", L10n.tr("Bank of England")), ("ons", "ONS"), ("nomis", "Nomis"), ("octopus", "Octopus Energy"),
        ("frankfurter", "Frankfurter"), ("boe-mpc", L10n.tr("Bank of England MPC dates")),
    ] }

    static var studentSourceIDs: Set<String> { Set(studentSources.map(\.id)) }

    /// "Official facts" first (fixed figures checked by hand, not a live feed), then the student-facing
    /// sources from `GET /v1/sources` in a fixed order. Every other source is hidden.
    static func dataRows(_ sources: [SourceStatus]) -> [YouViewState.DataRow] {
        let facts = YouViewState.DataRow(
            id: "facts", name: L10n.tr("Official facts (gov.uk, SAAS, Student Finance)"), status: .cached,
            detail: L10n.tr("Checked figures")
        )
        let byID = Dictionary(sources.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        return [facts] + studentSources.compactMap { item in
            byID[item.id].map { source in
                var row = dataRow(source)
                row.name = item.name
                return row
            }
        }
    }

    static func dataRow(_ source: SourceStatus) -> YouViewState.DataRow {
        let status = StateMapping.status(source.status.rawValue)
        let detail: String = switch status {
        case .live: L10n.tr("Live")
        case .cached: L10n.tr("Saved copy")
        case .mock: L10n.tr("Not live now")
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

    /// The header name (PENNY_V3_BUILD G1): the student's name, never "You". A placeholder character name
    /// ("You" or empty) falls back to the account's display name.
    static func profile(_ profile: FinanceProfile, displayName: String? = nil) -> YouViewState.Profile {
        let character = profile.character
        let placeholder = character.name.isEmpty || character.name == "You"
        let name = placeholder ? (displayName.flatMap { $0.isEmpty ? nil : $0 } ?? character.name) : character.name
        let decision = profile.profile
        let housing = housingLabel(decision.housing.rawValue)
        return .init(
            emoji: character.emoji ?? "🙂",
            name: name,
            detail: profileLine(age: decision.age, isStudent: profile.isStudent, occupation: character.occupation, housing: decision.housing.rawValue),
            annualIncome: decision.annualIncome,
            savings: decision.savings,
            housingText: housing
        )
    }
}
