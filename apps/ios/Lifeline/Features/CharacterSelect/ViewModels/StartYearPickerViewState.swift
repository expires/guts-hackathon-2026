import Foundation

struct StartYearPickerViewState: Equatable, Sendable {
    var emoji: String
    var name: String
    var occupation: String
    var town: String
    var birthYear: Int
    var years: ClosedRange<Int>
    var selectedYear: Int
    var ageAtStart: Int
    var isStarting: Bool
    var usesSampleData: Bool
}

struct StartYearPickerActions {
    var onYearChange: @MainActor (Int) -> Void = { _ in }
    var onStart: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
