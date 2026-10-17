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
    private(set) var phase: LoadPhase = .loading(.init(message: YouViewModel.loadingMessage))
    @ObservationIgnored var onRoute: @MainActor (Route) -> Void = { _ in }

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: YouViewState {
        Self.makeState(profile: profile, phase: phase, clientKind: client.kind, isDebugBuild: ClientFactory.isDebugBuild)
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
        do {
            profile = try await client.financeProfile()
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

    static func makeState(profile: FinanceProfile?, phase: LoadPhase, clientKind: ClientKind, isDebugBuild: Bool) -> YouViewState {
        let isSample = profile.map { FinanceMapping.isSample($0.meta) } ?? (clientKind == .mock)
        return YouViewState(
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
