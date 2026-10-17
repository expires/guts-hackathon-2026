import SwiftUI

/// Glue: owns `AccountsViewModel`, opens the Monzo sign-in in Safari and handles the return.
///
/// Monzo signs you in with an emailed magic link, so the URL opens in Safari with `openURL`.
/// `ASWebAuthenticationSession` would not see the link open in Mail or Safari.
struct AccountsScreen: View {
    @State private var model: AccountsViewModel
    @Environment(\.openURL) private var openURL
    @Environment(AppCoordinator.self) private var coordinator
    @Environment(\.scenePhase) private var scenePhase
    private let onClose: @MainActor () -> Void
    private let onConnectionsChanged: @MainActor () -> Void

    init(
        client: any LifelineClient,
        onConnectionsChanged: @escaping @MainActor () -> Void = {},
        onClose: @escaping @MainActor () -> Void
    ) {
        _model = State(initialValue: AccountsViewModel(client: client))
        self.onConnectionsChanged = onConnectionsChanged
        self.onClose = onClose
    }

    var body: some View {
        AccountsView(state: model.state, actions: model.actions)
            .task {
                model.onClose = onClose
                model.onConnectionsChanged = onConnectionsChanged
                await model.load()
                if let result = coordinator.takePendingReturn() { await model.handle(result) }
            }
            .onChange(of: coordinator.returnCount) {
                guard let result = coordinator.takePendingReturn() else { return }
                Task { await model.handle(result) }
            }
            .onChange(of: model.consentURL) { _, url in
                guard let url else { return }
                openURL(url)
                model.consentURLOpened()
            }
            // Coming back from Safari without the deep link (e.g. the app switcher) still refreshes:
            // the sign-in is stored server-side, so a reload picks it up.
            .onChange(of: scenePhase) { _, phase in
                guard phase == .active else { return }
                Task {
                    await model.load()
                    model.startSyncIfNeeded()
                    onConnectionsChanged()
                }
            }
            .onAppear { model.startSyncIfNeeded() }
            .onDisappear { model.stopSync() }
    }
}
