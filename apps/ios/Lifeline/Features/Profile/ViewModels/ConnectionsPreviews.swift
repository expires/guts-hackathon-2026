import Foundation

/// Fixture states for the connect step (previews, Playground, screenshots).
@MainActor enum ConnectionsPreviews {
    static func state(_ scenario: ProfileFixtures.Scenario, continueTitle: String? = nil) -> ConnectionsViewState {
        var state = ConnectionsViewState()
        let stats = ProfileFixtures.stats(scenario)
        state.rows = ConnectionsViewModel.makeRows(stats: stats, providers: [])
        state.sampleNote = ConnectionsViewModel.sampleNote(stats: stats)
        state.phase = .ready
        state.continueTitle = continueTitle
        return state
    }

    static var nothing: ConnectionsViewState { state(.nothing) }
    static var connected: ConnectionsViewState { state(.monzoAndT212) }
    static var withContinue: ConnectionsViewState {
        var s = state(.t212Only, continueTitle: L10n.tr("Continue"))
        s.highlighted = .monzo
        return s
    }
    static var sample: ConnectionsViewState { state(.sampleStudent, continueTitle: L10n.tr("Continue")) }
    static var confirming: ConnectionsViewState {
        var s = state(.monzoAndT212)
        s.pendingDisconnect = .trading212
        return s
    }
}
