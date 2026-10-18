import Foundation

/// Fixture states for "Who are you playing as?".
@MainActor enum ProfilePickerPreviews {
    static func state(_ scenario: ProfileFixtures.Scenario) -> ProfilePickerViewState {
        var state = ProfilePickerViewState()
        state.cards = ProfilePickerViewModel.makeCards(samples: MockExamples.samples, stats: ProfileFixtures.stats(scenario))
        state.phase = .ready
        return state
    }

    static var nothingActive: ProfilePickerViewState { state(.nothing) }
    static var sampleActive: ProfilePickerViewState { state(.sampleStudent) }
    static var youActive: ProfilePickerViewState { state(.monzoAndT212) }
    static var importing: ProfilePickerViewState {
        var s = state(.nothing)
        s.busyID = s.cards.dropFirst().first?.id
        return s
    }
}
