import Foundation

/// Play tab fixtures (W9, ADR 0052).
@MainActor
enum PlayFixturesW7 {
    /// Play solo, Play with friends and Join, with a "Back to room" card.
    static var withRoom: PlayViewState {
        var state = Fixtures.Play.ready
        state.rooms = RoomFlowFixtures.entryActive
        return state
    }

    /// Play solo, Play with friends and Join, no open room.
    static var withEntry: PlayViewState {
        var state = Fixtures.Play.ready
        state.rooms = RoomFlowFixtures.entryReady
        state.circles = RoomFlowFixtures.circles
        state.learn = LearnFixtures.entry
        return state
    }
}
