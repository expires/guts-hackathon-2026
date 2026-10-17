import Foundation

struct EventSheetViewState: Equatable, Sendable {
    struct Choice: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String?
        var label: String
        /// Plain English cost or effect, for example "-£540 a year".
        var hint: String?
        var isDefault: Bool
        /// "£695": the monthly payment for this choice, from the event facts (`pay_<option>`). Nil when unknown.
        var amountText: String? = nil
        /// "a month".
        var amountCaption: String? = nil
    }

    var id: String
    var emoji: String
    var year: Int
    var age: Int
    var title: String
    var text: String
    /// True when an AI wrote the words. Numbers still come from the engine.
    var isAIText: Bool
    var choices: [Choice]
    /// Source chips. Notes such as "UK average used" are in `SourceChipState.note`.
    var sources: [SourceChipState]
    var isSubmitting: Bool
    /// Life area for the colour band: work, home, money, family, health or other.
    var area: String = "other"
    var areaLabel: String = "Life"
    /// "2021 · Age 29".
    var dateText: String = ""
    /// The choice the player tapped, while it is sent. It shows "Chosen" with a tick; the others dim.
    var chosenID: String? = nil
}

struct EventSheetActions {
    var onChoose: @MainActor (String) -> Void = { _ in }
    /// Closes the full-screen event without choosing (it stays open on the feed).
    var onClose: @MainActor () -> Void = {}
    /// "Not sure? Ask Penny". Nil hides the button.
    var onAskPenny: (@MainActor () -> Void)?

    static var noop: Self { .init() }
}
