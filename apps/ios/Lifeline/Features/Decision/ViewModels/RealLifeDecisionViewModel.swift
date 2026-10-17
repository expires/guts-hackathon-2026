import Foundation
import Observation

/// Real-life Decision: one clear recommended action with evidence (`POST /v1/decisions`).
///
/// Entry points (ADR 0018):
/// - "Why?" on a mortgage Next Move: context `.whyMove`, profile from the move's character.
///   "Test it" opens the comparison for the same move.
/// - A "Play yourself" life reaches the present: context `.playYourself`, `lifeID` set.
/// - Money tab or menus: context `.money`.
@MainActor
@Observable
final class RealLifeDecisionViewModel {
    static let loadingMessage = "Comparing with similar lives"

    private let client: any LifelineClient
    private let profile: DecisionProfile
    private let lifeID: String?
    let context: DecisionContext
    /// Set for `.whyMove`. Enables "Test it".
    let moveID: String?
    private(set) var decision: Decision?
    private(set) var phase: LoadPhase = .loading(.init(message: RealLifeDecisionViewModel.loadingMessage))
    private var generation = 0
    @ObservationIgnored var onClose: @MainActor () -> Void = {}
    /// Called with `moveID` when the player taps "Test it".
    var onTestIt: (@MainActor (String) -> Void)?

    /// Original entry point. Context is `.playYourself` when `lifeID` is set, else `.money`.
    convenience init(client: any LifelineClient, profile: DecisionProfile, lifeID: String?) {
        self.init(client: client, profile: profile, lifeID: lifeID, context: lifeID == nil ? .money : .playYourself)
    }

    init(client: any LifelineClient, profile: DecisionProfile, lifeID: String?, context: DecisionContext, moveID: String? = nil) {
        self.client = client
        self.profile = profile
        self.lifeID = lifeID
        self.context = context
        self.moveID = moveID
    }

    var state: RealLifeDecisionViewState {
        Self.makeState(
            decision: decision,
            phase: phase,
            context: context,
            canTestIt: context == .whyMove && moveID != nil && onTestIt != nil
        )
    }

    var actions: RealLifeDecisionActions {
        RealLifeDecisionActions(
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() },
            onTestIt: { [weak self] in
                guard let self, let moveID = self.moveID else { return }
                self.onTestIt?(moveID)
            }
        )
    }

    func load() async {
        generation += 1
        let current = generation
        phase = .loading(.init(message: Self.loadingMessage))
        do {
            let value = try await client.createDecision(profile: profile, lifeID: lifeID)
            guard current == generation else { return }
            decision = value
            phase = .ready
        } catch is CancellationError {
            return
        } catch {
            guard current == generation else { return }
            phase = .failed(.from(APIError.map(error)))
        }
    }

    // MARK: Mapping (pure)

    /// Plain English names for decision action ids.
    static func actionLabel(_ id: String) -> String {
        switch id {
        case "fix_2y": "Fix for 2 years"
        case "fix_5y": "Fix for 5 years"
        case "tracker": "Tracker rate"
        default: id.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    static func title(for context: DecisionContext) -> String {
        switch context {
        case .money: "Your real decision"
        case .whyMove: "Why this move?"
        case .playYourself: "You reached today"
        }
    }

    /// 0.7 -> "7 in 10". Rounds to the nearest tenth.
    static func successText(_ rate: Double) -> String {
        "\(Int((min(1, max(0, rate)) * 10).rounded())) in 10"
    }

    /// "Based on 40 similar lives in 1989-1991, 2006-2008 and 2022-2024."
    static func basisSentence(twins: Int, periods: [String]) -> String {
        let lives = twins == 1 ? "1 similar life" : "\(twins) similar lives"
        guard !periods.isEmpty else { return "Based on \(lives)." }
        let joined = periods.count == 1
            ? periods[0]
            : periods.dropLast().joined(separator: ", ") + " and " + periods[periods.count - 1]
        return "Based on \(lives) in \(joined)."
    }

    static func makeState(
        decision: Decision?,
        phase: LoadPhase,
        context: DecisionContext = .money,
        canTestIt: Bool = false
    ) -> RealLifeDecisionViewState {
        let title = title(for: context)
        guard let decision else {
            return RealLifeDecisionViewState(
                phase: phase, question: "", headline: "", reasons: [], evidenceSentence: "", successRate: 0,
                twinsCount: 0, periods: [], alternatives: [], sources: [], disclaimer: "",
                context: context, title: title, canTestIt: false
            )
        }
        let sources = decision.sources.map(StateMapping.sourceChip)
        return RealLifeDecisionViewState(
            phase: phase,
            question: decision.question,
            headline: decision.headline,
            reasons: decision.reasons,
            evidenceSentence: decision.evidence.sentence,
            successRate: decision.evidence.successRate,
            twinsCount: decision.evidence.twinsCount,
            periods: decision.evidence.periods,
            alternatives: decision.alternatives.map { .init(id: $0.action, label: actionLabel($0.action), successRate: $0.successRate) },
            sources: sources,
            disclaimer: decision.disclaimer,
            context: context,
            title: title,
            actionID: decision.action,
            successText: successText(decision.evidence.successRate),
            basisSentence: basisSentence(twins: decision.evidence.twinsCount, periods: decision.evidence.periods),
            canTestIt: canTestIt,
            isSampleData: sources.contains { $0.status == .mock }
        )
    }
}

/// Builds `DecisionProfile` from the profile character (`GET /v1/finance/profile` or `TestMoveResult.character`).
/// Used by the "Why?" entry point. Values are clamped to the contract limits.
enum DecisionProfileMapping {
    static func profile(
        from character: CharacterSpec,
        currentYear: Int,
        dealEndsInMonths: Int? = nil,
        mortgageYearsLeft: Int? = nil
    ) -> DecisionProfile {
        let property = character.propertyValue ?? 0
        let mortgage = character.mortgageBalance ?? 0
        return DecisionProfile(
            age: min(100, max(16, currentYear - character.birthYear)),
            region: character.region,
            postcode: character.postcode,
            annualIncome: min(10_000_000, max(0, character.annualIncome)),
            savings: min(100_000_000, max(0, character.savings ?? 0)),
            otherDebt: min(100_000_000, max(0, character.debt ?? 0)),
            housing: DecisionProfile.HousingPayload(rawValue: character.housing?.rawValue ?? "rent") ?? .rent,
            propertyValue: property > 0 ? min(100_000_000, property) : nil,
            mortgageBalance: mortgage > 0 ? min(100_000_000, mortgage) : nil,
            mortgageYearsLeft: mortgageYearsLeft.map { min(40, max(0, $0)) },
            dealEndsInMonths: dealEndsInMonths.map { min(120, max(0, $0)) }
        )
    }

    /// `Move.days_left` to whole months, rounded up: 165 days -> 6 months.
    static func months(fromDaysLeft days: Int) -> Int {
        guard days > 0 else { return 0 }
        return Int((Double(days) / (365.25 / 12)).rounded(.up))
    }
}
