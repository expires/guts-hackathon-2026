import Foundation
import Observation

/// Rewind: pick a past decision, go back, take the other path.
@MainActor
@Observable
final class RewindViewModel {
    private let session: GameSession
    private(set) var result: RewindResultViewState?
    /// The decision the player looks at. Nil means the newest.
    private(set) var selectedID: String?
    @ObservationIgnored var onClose: @MainActor () -> Void = {}
    @ObservationIgnored var onBuyPass: @MainActor () -> Void = {}

    init(session: GameSession, decisionID: String? = nil) {
        self.session = session
        self.selectedID = decisionID
    }

    var pickerState: RewindPickerViewState {
        guard let life = session.life else {
            return RewindPickerViewState(options: [], allowanceText: "", needsPass: false, isSubmitting: false)
        }
        return Self.makePickerState(
            life: life,
            hasPass: session.hasRewindPass,
            isSubmitting: session.isBusy,
            selectedID: selectedID,
            usesSampleData: session.usesSampleData
        )
    }

    var actions: RewindActions {
        RewindActions(
            onPick: { [weak self] id in Task { await self?.rewind(to: id) } },
            onBuyPass: { [weak self] in self?.onBuyPass() },
            onClose: { [weak self] in self?.onClose() },
            onSelect: { [weak self] id in self?.selectedID = id }
        )
    }

    func rewind(to decisionID: String) async {
        guard let result = await session.rewind(decisionID: decisionID) else { return }
        self.result = Self.makeResultState(result)
    }

    static func makePickerState(
        life: Life,
        hasPass: Bool,
        isSubmitting: Bool,
        selectedID: String? = nil,
        usesSampleData: Bool = false
    ) -> RewindPickerViewState {
        let options = life.history.compactMap { entry -> RewindPickerViewState.Option? in
            guard let id = entry.decisionId else { return nil }
            return .init(
                id: id, year: entry.year, age: entry.age, text: entry.text,
                netWorth: entry.netWorth, index: entry.index, choiceID: entry.choiceId
            )
        }.reversed() as [RewindPickerViewState.Option]
        let pass = hasPass || life.rewind.hasPass == true
        let allowance: String
        if pass {
            allowance = L10n.tr("Rewind Pass: unlimited rewinds")
        } else if life.rewind.freeLeft == 1 {
            allowance = L10n.tr("1 free rewind left")
        } else {
            allowance = L10n.tr("\(life.rewind.freeLeft) free rewinds left")
        }
        let selected = options.first { $0.id == selectedID } ?? options.first
        let gap = (life.index.value - autopilotIndex).rounded()
        return RewindPickerViewState(
            options: options,
            allowanceText: allowance,
            needsPass: !pass && life.rewind.freeLeft <= 0,
            isSubmitting: isSubmitting,
            selectedID: selected?.id,
            timeline: selected.map { timeline(from: $0.year, to: life.year) } ?? [],
            didLines: selected.map(didLines) ?? [],
            alternative: selected.map { alternative($0) },
            indexNow: life.index.value,
            autopilotIndex: autopilotIndex,
            indexGapText: gap == 0 ? L10n.tr("Level") : (gap < 0 ? L10n.tr("\(Int(abs(gap))) behind") : L10n.tr("\(Int(abs(gap))) ahead")),
            isBehind: gap < 0,
            isSampleData: usesSampleData
        )
    }

    /// The autopilot twin's Lifeline Index. 100 by definition (docs/index.md).
    static let autopilotIndex: Double = 100

    /// Up to 4 labels from the decision year to now. The last label is "Now".
    static func timeline(from start: Int, to now: Int) -> [String] {
        guard now > start else { return [String(start), "Now"] }
        let span = now - start
        let steps = min(span, 3)
        var labels = (0..<steps).map { String(start + Int((Double($0) * Double(span) / Double(steps)).rounded())) }
        labels.append("Now")
        return labels
    }

    static func didLines(_ option: RewindPickerViewState.Option) -> [String] {
        [
            L10n.tr("Net worth then \(Money.format(option.netWorth))"),
            L10n.tr("Index then \(Int(option.index.rounded()))"),
        ]
    }

    /// Fixture card for known mortgage choices, otherwise a plain "other choice" card with no numbers.
    static func alternative(
        _ option: RewindPickerViewState.Option,
        table: [String: RewindAlternative] = RewindAlternatives.byChoice
    ) -> RewindPickerViewState.Alternative {
        guard let choice = option.choiceID, let alt = table[choice] else {
            return .init(
                title: "The other choice",
                lines: [L10n.tr("Same start in \(String(option.year))"), "You choose again"],
                source: nil
            )
        }
        // The % sign sits in the value, so the localisation key has no bare "%".
        let rate = alt.ratePercent.formatted(.number.locale(Money.locale).precision(.fractionLength(2))) + "%"
        let lines: [String?] = [
            L10n.tr("Rate \(rate)"),
            alt.monthlyPayment.map { L10n.tr("\(String(option.year)): \(Money.format($0.amount)) a month") },
            L10n.tr("Next choice: \(String(option.year + alt.fixYears))"),
        ]
        return .init(
            title: alt.title, lines: lines.compactMap { $0 }, source: alt.source, paymentSource: alt.monthlyPayment?.source
        )
    }

    static func makeResultState(_ result: RewindResult) -> RewindResultViewState {
        RewindResultViewState(
            year: result.life.year,
            age: result.life.age,
            abandonedIndex: result.abandonedIndex,
            newIndex: result.life.index.value,
            abandonedNetWorth: result.abandonedNetWorth,
            newNetWorth: result.life.finances.netWorth,
            message: L10n.tr("You are back in \(String(result.life.year)), age \(result.life.age). Choose again.")
        )
    }
}
