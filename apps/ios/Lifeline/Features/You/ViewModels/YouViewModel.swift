import Foundation
import Observation

/// Loads `GET /v1/finance/profile` for the You tab and routes to settings screens.
@MainActor
@Observable
final class YouViewModel {
    enum Route: Equatable {
        case bank, plan, sources, evaluation, spendAccuracy, store, debug, connectMoney, askPenny, aiDisclosure, newPlayer, resetDemo, account
    }

    static let loadingMessage = "Loading your profile"

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
            evaluationCount: evaluationCount
        )
    }

    var actions: YouActions {
        YouActions(
            onConnectMoney: { [weak self] in self?.onRoute(.connectMoney) },
            onOpenAccount: { [weak self] in self?.onRoute(.account) },
            onAskPenny: { [weak self] in self?.onRoute(.askPenny) },
            onNewPlayer: { [weak self] in self?.onRoute(.newPlayer) },
            onResetDemo: { [weak self] in self?.onRoute(.resetDemo) },
            onOpenAIDisclosure: { [weak self] in self?.onRoute(.aiDisclosure) },
            onRefresh: { [weak self] in await self?.load() },
            onConnectBank: { [weak self] in self?.onRoute(.bank) },
            onOpenPlan: { [weak self] in self?.onRoute(.plan) },
            onOpenSources: { [weak self] in self?.onRoute(.sources) },
            onOpenEvaluation: { [weak self] in self?.onRoute(.evaluation) },
            onOpenSpendAccuracy: { [weak self] in self?.onRoute(.spendAccuracy) },
            onOpenStore: { [weak self] in self?.onRoute(.store) },
            onOpenDebug: { [weak self] in
                if ClientFactory.isDebugBuild { self?.onRoute(.debug) }
            },
            onRetry: { [weak self] in Task { await self?.load() } }
        )
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
        if let value = try? await lives { self.lives = value.lives }
        if let value = try? await evaluation { evaluationCount = value.n }
    }

    /// Calm error for the You tab. Never shows rate-limit or server wording.
    static func calmError(_ error: APIError) -> ErrorViewState {
        let mapped = ErrorViewState.from(error)
        if mapped.isUnavailable { return mapped }
        return ErrorViewState(title: "Couldn't load", message: "Pull to refresh.", canRetry: true)
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
                ? "Not connected. The Money tab shows sample data."
                : "Connected. The Money tab uses your bank data.",
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
        state.dataBadgeText = profile.flatMap { FinanceMapping.badgeText($0.meta) } ?? (profile == nil && clientKind == .mock ? "Mock data" : nil)
        state.showsEvaluation = (evaluationCount ?? 0) > 0
        state.credits = creditLines(credits)
        state.buildInfo = buildInfo
        state.connectMoneyText = connectMoneyText
        return state
    }

    static let connectMoneyError = "Couldn't load. Pull to refresh."

    /// `Me.finance_inputs` to one calm line. No bank connections in V2 (ADR 0046): a statement wins over
    /// manual entry. Nil inputs: still loading (nil) or failed (the calm error, never the raw API message).
    static func connectMoneyText(inputs: [String]?, failed: Bool) -> String? {
        guard let inputs else { return failed ? connectMoneyError : nil }
        if inputs.contains("sample") { return "Sample statement" }
        if inputs.contains("statement") { return "Statement imported" }
        if inputs.contains("manual") { return "Entered by hand" }
        if !inputs.isEmpty { return "Money added" }
        return "Not added yet"
    }

    /// Onboarding's words for housing (DIRECTION_V2 section 4).
    static func housingLabel(_ raw: String) -> String {
        switch raw {
        case "rent": "Renting"
        case "parents": "Lives with family"
        case "own": "Owns a home"
        case "mortgage": "Has a mortgage"
        default: raw.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    /// "Age 20 · Student · Renting": the three things onboarding asks (bug 7, ADR 0053).
    /// `isStudent` from onboarding wins; the occupation text is the fallback when it is nil.
    static func profileLine(age: Int, isStudent: Bool? = nil, occupation: String, housing: String) -> String {
        let student = isStudent ?? occupation.lowercased().contains("student")
        let work = student ? "Student" : "Working"
        return ["Age \(age)", work, housingLabel(housing)].joined(separator: " · ")
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
        case .live: "Live"
        case .cached: "Saved copy"
        case .mock: "Mock data"
        case .unavailable: "Unavailable"
        }
        return .init(id: source.id, name: source.name, status: status, detail: detail)
    }

    /// Credits sentence plus one line per font licence. Empty when the file is missing.
    static func creditLines(_ credits: CreditsFile?) -> [String] {
        guard let credits else { return [] }
        return ["Credits: rates from the Bank of England. Icons, characters and design by the \(Brand.productName) team. Made in 24 hours at \(credits.event)."]
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
