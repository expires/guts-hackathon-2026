import SwiftUI

/// Glue: owns `RivalStripViewModel` and feeds `RivalStripView`.
struct RivalStripScreen: View {
    @State private var model: RivalStripViewModel

    init(players: [Components.Schemas.Player], myID: String?) {
        _model = State(initialValue: RivalStripViewModel(players: players, myID: myID))
    }

    var body: some View {
        RivalStripView(state: model.state)
    }
}
