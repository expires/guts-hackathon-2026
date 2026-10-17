import SwiftUI

/// Glue: owns `BankConnectViewModel` and feeds `BankConnectView`. Opens the consent URL in live mode.
struct BankConnectScreen: View {
    @State private var model: BankConnectViewModel
    @Environment(\.openURL) private var openURL
    @Environment(AppCoordinator.self) private var coordinator
    private let onUseProfile: @MainActor (DecisionProfile, DataStatus) -> Void
    private let onClose: @MainActor () -> Void

    init(
        client: any LifelineClient,
        onUseProfile: @escaping @MainActor (DecisionProfile, DataStatus) -> Void,
        onClose: @escaping @MainActor () -> Void
    ) {
        _model = State(initialValue: BankConnectViewModel(client: client))
        self.onUseProfile = onUseProfile
        self.onClose = onClose
    }

    var body: some View {
        BankConnectView(state: model.state, actions: model.actions)
            .onAppear {
                model.onUseProfile = onUseProfile
                model.onClose = onClose
            }
            .onChange(of: model.consentURL) { _, url in
                guard let url else { return }
                // Monzo emails a sign-in link, so this opens in Safari. The return lands in `AppCoordinator`.
                coordinator.bankFlowAwaitingReturn = true
                openURL(url)
            }
            .onChange(of: coordinator.returnCount) {
                guard let result = coordinator.takeBankFlowReturn() else { return }
                coordinator.bankFlowAwaitingReturn = false
                Task { await model.handle(result) }
            }
            .onDisappear { coordinator.bankFlowAwaitingReturn = false }
    }
}
