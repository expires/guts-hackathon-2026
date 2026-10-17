import Foundation
import Observation

/// Loads one "Test it" result: `POST /v1/next-move/test`.
/// Arguments: the move id and the option ids (nil means every option of the move).
/// The glue passes `client.testNextMove(moveID:optionIDs:)`. Tests and the Playground pass a fixture.
typealias TestItLoader = @Sendable (_ moveID: String, _ optionIDs: [String]?) async throws -> Components.Schemas.TestMoveResult

/// "Test it" comparison (ADR 0018). Plays every option of one move through the same past period
/// and shows the outcomes side by side. Every number comes from the API.
@MainActor
@Observable
final class TestItViewModel {
    static let loadingMessage = "Playing each option through a past period"

    let moveID: String
    private let optionIDs: [String]?
    private let loader: TestItLoader
    private(set) var result: Components.Schemas.TestMoveResult?
    private(set) var phase: LoadPhase = .loading(.init(message: TestItViewModel.loadingMessage))
    /// Increments on every load. A late response from an older load is dropped.
    private var generation = 0

    @ObservationIgnored var onOpenLife: @MainActor (String) -> Void = { _ in }
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(moveID: String, optionIDs: [String]? = nil, load: @escaping TestItLoader) {
        self.moveID = moveID
        self.optionIDs = optionIDs
        self.loader = load
    }

    var state: TestItViewState {
        Self.makeState(result: result, phase: phase)
    }

    var actions: TestItActions {
        TestItActions(
            onRetry: { [weak self] in Task { await self?.load() } },
            onOpenLife: { [weak self] lifeID in self?.onOpenLife(lifeID) },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    func load() async {
        generation += 1
        let current = generation
        phase = .loading(.init(message: Self.loadingMessage))
        do {
            let value = try await loader(moveID, optionIDs)
            guard current == generation else { return }
            result = value
            phase = value.outcomes.isEmpty ? .failed(Self.emptyError) : .ready
        } catch is CancellationError {
            return
        } catch {
            guard current == generation else { return }
            phase = .failed(.from(APIError.map(error)))
        }
    }

    // MARK: Mapping (pure, used by fixtures and tests)

    static let emptyError = ErrorViewState(
        title: "Nothing to compare",
        message: "This move has no options to test yet.",
        canRetry: true
    )

    static func makeState(result: Components.Schemas.TestMoveResult?, phase: LoadPhase) -> TestItViewState {
        guard let result else {
            return TestItViewState(
                phase: phase, title: "Test it", periodLabel: "", periodSentence: "", options: [],
                recommendedID: nil, summary: "", evidenceSentence: "", sources: [], isSampleData: false,
                chartMin: 0, chartMax: 1
            )
        }
        let options = result.outcomes.map { option(for: $0, among: result.outcomes) }
        let sources = result.sources.map(StateMapping.sourceChip)
        let values = options.flatMap { $0.path.map(\.netWorth) }
        let (low, high) = chartRange(values)
        return TestItViewState(
            phase: phase,
            title: "Test it",
            periodLabel: result.period.label,
            periodSentence: periodSentence(start: result.period.start, end: result.period.end),
            options: options,
            recommendedID: options.first(where: \.isRecommended)?.id,
            summary: result.summary,
            evidenceSentence: result.evidenceSentence,
            sources: sources,
            isSampleData: sources.contains { $0.status == .mock },
            chartMin: low,
            chartMax: high
        )
    }

    static func periodSentence(start: Int, end: Int) -> String {
        start == end
            ? "We played your money through \(start)."
            : "We played your money through \(start) to \(end)."
    }

    static func option(
        for outcome: Components.Schemas.OptionOutcome,
        among all: [Components.Schemas.OptionOutcome]
    ) -> TestItViewState.Option {
        let path = outcome.netWorthPath.compactMap(pathPoint)
        let others = all.filter { $0.optionId != outcome.optionId }.map(\.endNetWorth)
        let gap = others.max().map { outcome.endNetWorth - $0 }
        let facts = facts(for: outcome)
        var spoken = [outcome.label]
        if outcome.isRecommended { spoken.append("Recommended") }
        spoken.append(contentsOf: facts)
        if let gap { spoken.append(gapSentence(gap)) }
        return TestItViewState.Option(
            id: outcome.optionId,
            label: outcome.label,
            isRecommended: outcome.isRecommended,
            lifeID: outcome.lifeId,
            path: path,
            startNetWorth: path.first?.netWorth ?? outcome.endNetWorth,
            endNetWorth: outcome.endNetWorth,
            endNetWorthGap: gap,
            totalCost: outcome.totalCost,
            missedPayments: outcome.missedPayments,
            worstYear: outcome.worstYear,
            worstYearChange: outcome.worstYearChange,
            index: outcome.index,
            facts: facts,
            accessibilitySummary: spoken.joined(separator: ". ")
        )
    }

    static func facts(for outcome: Components.Schemas.OptionOutcome) -> [String] {
        [
            "Ended with \(Money.format(outcome.endNetWorth))",
            "Paid \(Money.format(outcome.totalCost))",
            missedPaymentsText(outcome.missedPayments),
            "Worst year \(outcome.worstYear): \(Money.signed(outcome.worstYearChange))",
            "Index \(indexText(outcome.index))",
        ]
    }

    static func missedPaymentsText(_ count: Int) -> String {
        switch count {
        case 0: "No missed payments"
        case 1: "1 missed payment"
        default: "\(count) missed payments"
        }
    }

    static func gapSentence(_ gap: Double) -> String {
        switch gap.rounded() {
        case 0: "Same as the other option"
        case let value where value > 0: "\(Money.format(value)) ahead of the next best"
        case let value: "\(Money.format(-value)) behind the best"
        }
    }

    /// One decimal place: "104.2".
    static func indexText(_ value: Double) -> String {
        value.formatted(.number.locale(Money.locale).precision(.fractionLength(1)))
    }

    /// Parses "yyyy-MM-dd" in UTC. Points with a bad date are dropped.
    static func pathPoint(_ point: Components.Schemas.Point) -> TestItViewState.PathPoint? {
        let parts = point.date.split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC") ?? .gmt
        guard let date = calendar.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2])) else { return nil }
        return .init(id: point.date, date: date, year: parts[0], netWorth: point.value)
    }

    /// Shared y range with 10% padding. A flat or empty series still gets a non-zero range.
    static func chartRange(_ values: [Double]) -> (Double, Double) {
        guard let low = values.min(), let high = values.max() else { return (0, 1) }
        let span = high - low
        let pad = span > 0 ? span * 0.1 : max(abs(high) * 0.1, 1)
        return (low - pad, high + pad)
    }
}
