import SwiftUI

/// Glue: owns `PeopleTabViewModel` and feeds `PeopleTabView`.
struct PeopleTabScreen: View {
    @State private var model: PeopleTabViewModel

    init(session: GameSession) {
        _model = State(initialValue: PeopleTabViewModel(session: session))
    }

    var body: some View {
        PeopleTabView(state: model.state, actions: model.actions)
    }
}
