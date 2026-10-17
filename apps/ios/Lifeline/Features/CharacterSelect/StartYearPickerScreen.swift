import SwiftUI

/// Glue: owns `StartYearPickerViewModel` and feeds `StartYearPickerView`.
struct StartYearPickerScreen: View {
    @State private var model: StartYearPickerViewModel

    init(choice: CharacterChoice, session: GameSession) {
        _model = State(initialValue: StartYearPickerViewModel(choice: choice, session: session))
    }

    var body: some View {
        StartYearPickerView(state: model.state, actions: model.actions)
    }
}
