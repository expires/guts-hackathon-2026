import SwiftUI

/// Glue: owns `MoneyTabViewModel` and feeds `MoneyTabView`.
struct MoneyTabScreen: View {
    @State private var model: MoneyTabViewModel
    private let onClose: @MainActor () -> Void

    init(session: GameSession, onClose: @escaping @MainActor () -> Void = {}) {
        _model = State(initialValue: MoneyTabViewModel(session: session))
        self.onClose = onClose
    }

    var body: some View {
        MoneyTabView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
    }
}
