import SwiftUI

/// Glue: owns `AssetsTabViewModel` and feeds `AssetsTabView`.
struct AssetsTabScreen: View {
    @State private var model: AssetsTabViewModel

    init(session: GameSession) {
        _model = State(initialValue: AssetsTabViewModel(session: session))
    }

    var body: some View {
        AssetsTabView(state: model.state, actions: model.actions)
    }
}
