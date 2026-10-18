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

    /// Presentation mode: amounts rounded, names generic. The glue sets it from `llPresentationMode`.
    var presentation = false
    @ObservationIgnored var onOpenLife: @MainActor (String) -> Void = { _ in }
    @ObservationIgnored var onClose: @MainActor () -> Void = {}
    /// Set by the glue when "Do this" can add the move to the plan. Nil hides the button.
    @ObservationIgnored var onDoThis: (@MainActor (String) -> Void)?

    init(moveID: String, optionIDs: [String]? = nil, load: @escaping TestItLoader) {
        self.moveID = moveID
        self.optionIDs = optionIDs
        self.loader = load
    }

    var state: TestItViewState {
        Self.makeState(result: result, phase: phase, canDoThis: onDoThis != nil, presentation: presentation)
    }

    var actions: TestItActions {
        TestItActions(
            onRetry: { [weak self] in Task { await self?.load() } },
            onOpenLife: { [weak self] lifeID in self?.onOpenLife(lifeID) },
            onClose: { [weak self] in self?.onClose() },
            onDoThis: { [weak self] in
                guard let self else { return }
                onDoThis?(moveID)
            }
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

    static func makeState(
        result: Components.Schemas.TestMoveResult?,
        phase: LoadPhase,
        canDoThis: Bool = false,
        presentation: Bool = false
    ) -> TestItViewState {
        guard let result else {
            return TestItViewState(
                phase: phase, title: "Test it", periodLabel: "", periodSentence: "", options: [],
                recommendedID: nil, summary: "", evidenceSentence: "", sources: [], isSampleData: false,
                chartMin: 0, chartMax: 1, canDoThis: canDoThis
            )
        }
        let birthYear = result.character.birthYear
        let options = result.outcomes.map {
            option(for: $0, among: result.outcomes, birthYear: birthYear, period: result.period, presentation: presentation)
        }
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
            summary: PresentationFormat.text(result.summary, presentation),
            evidenceSentence: PresentationFormat.text(result.evidenceSentence, presentation),
            sources: sources,
            isSampleData: sources.contains { $0.status == .mock },
            chartMin: low,
            chartMax: high,
            intro: intro(name: PresentationFormat.name(result.character.name, presentation), optionCount: options.count),
            faceEmoji: result.character.emoji,
            hero: hero(options: options, summary: PresentationFormat.text(result.summary, presentation), presentation: presentation),
            canDoThis: canDoThis
        )
    }

    /// "Two of you. Same life. One choice is different." Uses the character name when it is not "You".
    /// One full sentence per case, so each language translates the whole line (no English word fragments).
    static func intro(name: String, optionCount: Int) -> String {
        let isYou = name.isEmpty || name == "You"
        switch (optionCount, isYou) {
        case (2, true): return L10n.tr("Two of you. Same life. One choice is different.")
        case (3, true): return L10n.tr("Three of you. Same life. One choice is different.")
        case (4, true): return L10n.tr("Four of you. Same life. One choice is different.")
        case (2, false): return L10n.tr("Two versions of \(name). Same life. One choice is different.")
        case (3, false): return L10n.tr("Three versions of \(name). Same life. One choice is different.")
        case (4, false): return L10n.tr("Four versions of \(name). Same life. One choice is different.")
        default: return L10n.tr("One life. One choice.")
        }
    }

    /// Hero: total paid by the recommended option against the cheapest other option (the same pair as
    /// the API `summary`). The sentence under the amount is the API `summary`, verbatim.
    static func hero(options: [TestItViewState.Option], summary: String, presentation: Bool = false) -> TestItViewState.Hero? {
        guard options.count > 1, let best = options.first(where: \.isRecommended),
              let other = options.filter({ $0.id != best.id }).min(by: { $0.totalCost < $1.totalCost }) else { return nil }
        let difference = (best.totalCost - other.totalCost).rounded()
        guard abs(difference) >= 1 else { return nil }
        return .init(
            amount: abs(difference),
            amountText: PresentationFormat.money(abs(difference), presentation),
            caption: "\(difference > 0 ? "more" : "less") paid than \"\(other.label)\"",
            text: summary
        )
    }

    /// "from 2021 to 2023" or "in 2008".
    static func periodSpan(start: Int, end: Int) -> String {
        start == end ? "in \(start)" : "from \(start) to \(end)"
    }

    /// Story rows: one per path year after the first. Age comes from the character's birth year.
    static func yearRows(path: [TestItViewState.PathPoint], birthYear: Int?, presentation: Bool = false) -> [TestItViewState.YearRow] {
        let money = { (value: Double) in PresentationFormat.money(value, presentation) }
        return path.enumerated().map { offset, point -> TestItViewState.YearRow in
            let title = birthYear.map { L10n.tr("\(String(point.year)) · Age \(point.year - $0)") } ?? "\(point.year)"
            if offset == 0 {
                return .init(id: point.id, title: title, text: L10n.tr("I start with \(money(point.netWorth))."), change: nil, isDown: false)
            }
            let change = (point.netWorth - path[offset - 1].netWorth).rounded()
            let changeText: String? = change == 0 ? nil : (change > 0 ? "Up " : "Down ") + money(abs(change))
            return .init(id: point.id, title: title, text: L10n.tr("I have \(money(point.netWorth))."), change: changeText, isDown: change < 0)
        }
    }

    static func periodSentence(start: Int, end: Int) -> String {
        start == end
            ? L10n.tr("We played your money through \(String(start)).")
            : L10n.tr("We played your money through \(String(start)) to \(String(end)).")
    }

    static func option(
        for outcome: Components.Schemas.OptionOutcome,
        among all: [Components.Schemas.OptionOutcome],
        birthYear: Int? = nil,
        period: Components.Schemas.TestPeriod? = nil,
        presentation: Bool = false
    ) -> TestItViewState.Option {
        let path = outcome.netWorthPath.compactMap(pathPoint)
        let others = all.filter { $0.optionId != outcome.optionId }.map(\.endNetWorth)
        let gap = others.max().map { outcome.endNetWorth - $0 }
        let facts = facts(for: outcome, presentation: presentation)
        var spoken = [outcome.label]
        if outcome.isRecommended { spoken.append("Recommended") }
        spoken.append(contentsOf: facts)
        if let gap { spoken.append(gapSentence(gap, presentation: presentation)) }
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
            accessibilitySummary: spoken.joined(separator: ". "),
            yearRows: yearRows(path: path, birthYear: birthYear, presentation: presentation),
            costLabel: period.map { "Paid " + periodSpan(start: $0.start, end: $0.end) } ?? "Paid",
            indexLabel: L10n.tr("Index \(indexText(outcome.index))")
        )
    }

    static func facts(for outcome: Components.Schemas.OptionOutcome, presentation: Bool = false) -> [String] {
        [
            L10n.tr("Ended with \(PresentationFormat.money(outcome.endNetWorth, presentation))"),
            L10n.tr("Paid \(PresentationFormat.money(outcome.totalCost, presentation))"),
            missedPaymentsText(outcome.missedPayments),
            L10n.tr("Worst year \(String(outcome.worstYear)): \(PresentationFormat.money(outcome.worstYearChange, presentation, style: .signed))"),
            L10n.tr("Index \(indexText(outcome.index))"),
        ]
    }

    static func missedPaymentsText(_ count: Int) -> String {
        switch count {
        case 0: "No missed payments"
        case 1: "1 missed payment"
        default: "\(count) missed payments"
        }
    }

    static func gapSentence(_ gap: Double, presentation: Bool = false) -> String {
        switch gap.rounded() {
        case 0: "Same as the other option"
        case let value where value > 0: L10n.tr("\(PresentationFormat.money(value, presentation)) ahead of the next best")
        case let value: L10n.tr("\(PresentationFormat.money(-value, presentation)) behind the best")
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
