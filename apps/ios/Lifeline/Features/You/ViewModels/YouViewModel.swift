import Foundation
import Observation

/// Loads `GET /v1/finance/profile` for the You tab and routes to settings screens.
@MainActor
@Observable
final class YouViewModel {
    enum Route: Equatable {
        case bank, plan, sources, evaluation, spendAccuracy, store, debug
    }

    static let loadingMessage = "Loading your profile"

    private let client: any LifelineClient
    private(set) var profile: FinanceProfile?
    private(set) var lives: [LifeListItem] = []
    private(set) var conceptsTotal = 0
    private(set) var sources: [SourceStatus] = []
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
            lives: lives, conceptsUnlocked: conceptsUnlocked, conceptsTotal: conceptsTotal, sources: sources, credits: credits
        )
    }

    var actions: YouActions {
        YouActions(
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

    func load() async {
        phase = .loading(.init(message: Self.loadingMessage))
        async let lives = client.listLives()
        async let concepts = client.listConcepts()
        async let sources = client.listSources()
        do {
            profile = try await client.financeProfile()
            self.lives = (try? await lives)?.lives ?? []
            conceptsTotal = (try? await concepts)?.count ?? 0
            self.sources = (try? await sources) ?? []
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
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
        credits: CreditsFile? = nil
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
            state.personaLine = [isSample ? "Demo persona" : nil, mapped.detail, mapped.housingText]
                .compactMap { $0 }.joined(separator: " · ")
        }
        state.bestIndexText = best.map { "\(Int($0.rounded()))" } ?? "-"
        state.ribbonsText = "\(lives.reduce(0) { $0 + $1.ribbons })"
        state.conceptsText = conceptsTotal > 0 ? "\(unlocked)/\(conceptsTotal)" : "\(unlocked)"
        state.bankName = isSample ? "Demo Bank" : "Your bank"
        state.bankDetail = isSample ? "Fake accounts, not your bank" : "Connected"
        state.dataRows = sources.map(dataRow)
        state.credits = creditLines(credits)
        return state
    }

    static func dataRow(_ source: SourceStatus) -> YouViewState.DataRow {
        let status = StateMapping.status(source.status.rawValue)
        let detail: String = switch status {
        case .live: "Live"
        case .cached: "Saved copy"
        case .mock: "Mock data"
        }
        return .init(id: source.id, name: source.name, status: status, detail: detail)
    }

    /// Credits sentence plus one line per font licence. Empty when the file is missing.
    static func creditLines(_ credits: CreditsFile?) -> [String] {
        guard let credits else { return [] }
        return ["Credits: rates from the Bank of England. Icons, characters and design by the \(Brand.productName) team. Made in 30 hours at \(credits.event)."]
            + credits.fonts.map { "\($0.name) by \($0.authors). \($0.licence)." }
    }

    static func profile(_ profile: FinanceProfile) -> YouViewState.Profile {
        let character = profile.character
        let decision = profile.profile
        let housing: String = switch decision.housing.rawValue {
        case "rent": decision.monthlyRent.map { "Renting, \(Money.format($0)) a month" } ?? "Renting"
        case "mortgage", "own": "Own home"
        default: decision.housing.rawValue.replacingOccurrences(of: "_", with: " ").capitalized
        }
        return .init(
            emoji: character.emoji ?? "🙂",
            name: character.name,
            detail: "\(character.occupation.capitalized) in \(character.town), age \(decision.age)",
            annualIncome: decision.annualIncome,
            savings: decision.savings,
            housingText: housing
        )
    }
}
