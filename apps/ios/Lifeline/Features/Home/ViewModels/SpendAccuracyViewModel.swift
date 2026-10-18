import Foundation
import Observation

/// Loads `GET /v1/finance/prediction/evaluation`.
@MainActor
@Observable
final class SpendAccuracyViewModel {
    static var loadingMessage: String { L10n.tr("Loading the model test") }

    private let client: any LifelineClient
    private(set) var evaluation: PredictionEvaluation?
    private(set) var phase: LoadPhase = .loading(.init(message: SpendAccuracyViewModel.loadingMessage))
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: SpendAccuracyViewState { Self.makeState(evaluation: evaluation, phase: phase) }

    var actions: SpendAccuracyActions {
        SpendAccuracyActions(
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    func load() async {
        phase = .loading(.init(message: Self.loadingMessage))
        do {
            evaluation = try await client.predictionEvaluation()
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    static func makeState(evaluation: PredictionEvaluation?, phase: LoadPhase) -> SpendAccuracyViewState {
        guard let evaluation else {
            return SpendAccuracyViewState(
                phase: phase, method: "", daysText: "", mae: 0, baselineMAE: 0, modelText: "", baselineText: "",
                coverageText: "", days: [], isSampleData: false
            )
        }
        return SpendAccuracyViewState(
            phase: phase,
            method: evaluation.method,
            daysText: evaluation.nDays == 1 ? L10n.tr("Tested on 1 day") : L10n.tr("Tested on \(evaluation.nDays) days"),
            mae: evaluation.mae,
            baselineMAE: evaluation.baselineMae,
            modelText: L10n.tr("The model is off by \(FinanceMapping.pounds(evaluation.mae)) on a typical day."),
            baselineText: L10n.tr("\(evaluation.baseline) is off by \(FinanceMapping.pounds(evaluation.baselineMae))."),
            coverageText: L10n.tr("\(FinanceMapping.percent(evaluation.intervalCoverage)) of days fell inside the range."),
            days: evaluation.days.map { day in
                .init(
                    id: day.date, dateText: FinanceMapping.shortDayText(day.date), predicted: day.predicted,
                    low: day.low, high: day.high, actual: day.actual, baseline: day.baseline,
                    isInRange: day.actual >= day.low && day.actual <= day.high
                )
            },
            isSampleData: FinanceMapping.isSample(evaluation.meta)
        )
    }
}
