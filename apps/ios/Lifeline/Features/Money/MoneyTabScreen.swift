import SwiftUI

/// Glue: owns `MoneyTabViewModel` and feeds `MoneyTabView`.
struct MoneyTabScreen: View {
    @State private var model: MoneyTabViewModel

    init(session: GameSession) {
        _model = State(initialValue: MoneyTabViewModel(session: session))
    }

    var body: some View {
        MoneyTabView(state: model.state, actions: model.actions)
    }
}
