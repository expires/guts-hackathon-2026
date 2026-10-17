import Foundation

/// Play tab fixtures with the Same Life room (W7, ADR 0026).
@MainActor
enum PlayFixturesW7 {
    static var withRoom: PlayViewState {
        var state = Fixtures.Play.ready
        state.room = RoomsFixtures.lobby
        return state
    }
}
