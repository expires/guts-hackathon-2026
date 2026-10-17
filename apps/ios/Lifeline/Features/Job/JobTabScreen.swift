import SwiftUI

/// Glue: owns `JobTabViewModel` and feeds `JobTabView`.
struct JobTabScreen: View {
    @State private var model: JobTabViewModel

    init(session: GameSession) {
        _model = State(initialValue: JobTabViewModel(session: session))
    }

    var body: some View {
        JobTabView(state: model.state, actions: model.actions)
    }
}
