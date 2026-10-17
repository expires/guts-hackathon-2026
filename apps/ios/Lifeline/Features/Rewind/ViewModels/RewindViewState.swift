import Foundation

struct RewindPickerViewState: Equatable, Sendable {
    struct Option: Equatable, Sendable, Identifiable {
        /// The decision id sent to the backend.
        var id: String
        var year: Int
        var age: Int
        var text: String
        var netWorth: Double
        var index: Double
        /// Choice taken at this decision (`YearLog.choice_id`). Selects the "What I'll try" fixture.
        var choiceID: String? = nil
    }

    /// The "What I'll try" card for the selected decision.
    struct Alternative: Equatable, Sendable {
        var title: String
        var lines: [String]
        /// Where the alternative's rate comes from. Nil when the card has no number.
        var source: SourceChipState?
        /// Where the monthly payment comes from. Nil when the card shows no payment.
        var paymentSource: SourceChipState? = nil

        /// Every source on the card, rate first.
        var sources: [SourceChipState] { [source, paymentSource].compactMap { $0 } }
    }

    /// Past decisions, newest first.
    var options: [Option]
    /// For example "1 free rewind left" or "Rewind Pass: unlimited rewinds".
    var allowanceText: String
    /// True when the free rewind is used and there is no pass.
    var needsPass: Bool
    var isSubmitting: Bool
    /// The decision to go back to. Defaults to the newest.
    var selectedID: String? = nil
    /// Timeline labels from the selected year to now, for example ["2021", "2022", "2023", "Now"].
    var timeline: [String] = []
    /// "What I did" lines for the selected decision.
    var didLines: [String] = []
    var alternative: Alternative? = nil
    /// Lifeline Index now and the autopilot twin's (always 100, the baseline).
    var indexNow: Double = 100
    var autopilotIndex: Double = 100
    /// "4 behind" or "6 ahead" or "Level".
    var indexGapText: String = ""
    var isBehind: Bool = false
    var isSampleData: Bool = false

    var selected: Option? { options.first { $0.id == selectedID } ?? options.first }
}

struct RewindResultViewState: Equatable, Sendable {
    var year: Int
    var age: Int
    var abandonedIndex: Double
    var newIndex: Double
    var abandonedNetWorth: Double
    var newNetWorth: Double
    var message: String
}

struct RewindActions {
    var onPick: @MainActor (String) -> Void = { _ in }
    var onBuyPass: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}
    /// Selects a decision without rewinding.
    var onSelect: @MainActor (String) -> Void = { _ in }

    static var noop: Self { .init() }
}
