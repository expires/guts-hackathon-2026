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
    }

    /// Past decisions, newest first.
    var options: [Option]
    /// For example "1 free rewind left" or "Rewind Pass: unlimited rewinds".
    var allowanceText: String
    /// True when the free rewind is used and there is no pass.
    var needsPass: Bool
    var isSubmitting: Bool
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

    static var noop: Self { .init() }
}
