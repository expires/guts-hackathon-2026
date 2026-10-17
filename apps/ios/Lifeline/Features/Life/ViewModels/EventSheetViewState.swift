import Foundation

struct EventSheetViewState: Equatable, Sendable {
    struct Choice: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String?
        var label: String
        /// Plain English cost or effect, for example "-£540 a year".
        var hint: String?
        var isDefault: Bool
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
}

struct EventSheetActions {
    var onChoose: @MainActor (String) -> Void = { _ in }

    static var noop: Self { .init() }
}
