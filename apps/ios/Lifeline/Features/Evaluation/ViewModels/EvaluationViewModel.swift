import Foundation
import Observation

/// Loads `GET /v1/evaluation`.
@MainActor
@Observable
final class EvaluationViewModel {
    static var loadingMessage: String { L10n.tr("Loading the backtest") }

    private let client: any LifelineClient
    private(set) var evaluation: Evaluation?
    private(set) var phase: LoadPhase = .loading(.init(message: EvaluationViewModel.loadingMessage))
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: EvaluationViewState { Self.makeState(evaluation: evaluation, phase: phase) }

    var actions: EvaluationActions {
        EvaluationActions(
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    func load() async {
        phase = .loading(.init(message: Self.loadingMessage))
        do {
            evaluation = try await client.evaluation()
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    /// "fix_5y" -> "Fix 5y".
    static func optionLabel(_ id: String) -> String {
        let words = id.split(separator: "_").map(String.init)
        guard let first = words.first else { return id }
        return ([first.capitalized] + words.dropFirst()).joined(separator: " ")
    }

    static func makeState(evaluation: Evaluation?, phase: LoadPhase) -> EvaluationViewState {
        guard let evaluation else {
            return EvaluationViewState(
                phase: phase, method: "", hitRate: 0, baselineHitRate: 0, hitText: "", baselineText: "",
                periods: [], generatedText: ""
            )
        }
        let periodWord = evaluation.n == 1 ? "period" : "periods"
        return EvaluationViewState(
            phase: phase,
            method: evaluation.method,
            hitRate: evaluation.hitRate,
            baselineHitRate: evaluation.baselineHitRate,
            hitText: L10n.tr("Right in \(FinanceMapping.percent(evaluation.hitRate)) of \(evaluation.n) past \(periodWord)."),
            baselineText: L10n.tr("\(evaluation.baseline.prefix(1).uppercased() + evaluation.baseline.dropFirst()): right in \(FinanceMapping.percent(evaluation.baselineHitRate))."),
            periods: evaluation.periods.map { period in
                .init(
                    id: "\(period.start)-\(period.end)",
                    rangeText: "\(period.start) to \(period.end)",
                    detail: L10n.tr("Advice: \(optionLabel(period.recommended)). Best in hindsight: \(optionLabel(period.realisedBest))."),
                    isHit: period.hit
                )
            },
            generatedText: "Run on " + FinanceMapping.dayText(evaluation.generatedAt)
        )
    }
}
