import SwiftUI

/// Glue: owns `HabitsViewModel` and feeds `HabitsView`.
struct HabitsScreen: View {
    @State private var model: HabitsViewModel
    private let onClose: @MainActor () -> Void

    init(client: any LifelineClient, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: HabitsViewModel(client: client))
        self.onClose = onClose
    }

    var body: some View {
        HabitsView(state: model.state, actions: model.actions)
            .task {
                model.onClose = onClose
                await model.load()
            }
    }
}
