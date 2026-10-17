import SwiftUI

/// Glue: owns `CharacterFormViewModel` and feeds `CharacterFormView`.
struct CharacterFormScreen: View {
    @State private var model: CharacterFormViewModel
    @State private var showBank = false
    private let session: GameSession
    private let onContinue: @MainActor (CharacterChoice) -> Void

    init(mode: CharacterFormMode, session: GameSession, onContinue: @escaping @MainActor (CharacterChoice) -> Void) {
        _model = State(initialValue: CharacterFormViewModel(mode: mode))
        self.session = session
        self.onContinue = onContinue
    }

    var body: some View {
        CharacterFormView(state: model.state, actions: model.actions)
            .onAppear {
                model.onContinue = onContinue
                model.onConnectBank = { showBank = true }
            }
            .llCover(isPresented: $showBank) {
                BankConnectScreen(client: session.client) { profile, status in
                    model.apply(bankProfile: profile, status: status)
                    showBank = false
                } onClose: {
                    showBank = false
                }
            }
    }
}
