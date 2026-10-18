import Foundation

/// Fixture states for "Your profile".
@MainActor enum ProfileStatsPreviews {
    static func state(_ scenario: ProfileFixtures.Scenario) -> ProfileStatsViewState {
        ProfileStatsViewModel.makeState(ProfileFixtures.stats(scenario))
    }

    static var nothing: ProfileStatsViewState { state(.nothing) }
    static var t212Only: ProfileStatsViewState { state(.t212Only) }
    static var full: ProfileStatsViewState { state(.monzoAndT212) }
    static var sample: ProfileStatsViewState { state(.sampleStudent) }
}
