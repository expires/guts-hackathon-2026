import SwiftUI
import UniformTypeIdentifiers

/// Glue for the connect step. Owns `ConnectionsViewModel` and the platform parts: Safari for the Monzo sign-in,
/// the statement picker and the "Enter your numbers" form (onboarding's form, opened on its own).
struct ConnectionsScreen: View {
    @State private var model: ConnectionsViewModel
    @State private var showsPicker = false
    @State private var showsNumbers = false
    @Environment(\.openURL) private var openURL
    @Environment(\.scenePhase) private var scenePhase
    private let client: any LifelineClient
    private let onClose: @MainActor () -> Void
    private let onContinue: @MainActor () -> Void
    private let onChanged: @MainActor () -> Void

    /// - Parameter continueTitle: "Continue" to the stats page. Nil (You tab) shows no such button.
    init(
        client: any LifelineClient,
        continueTitle: String? = nil,
        highlighted: ConnectKind? = nil,
        onChanged: @escaping @MainActor () -> Void = {},
        onContinue: @escaping @MainActor () -> Void = {},
        onClose: @escaping @MainActor () -> Void
    ) {
        self.client = client
        self.onChanged = onChanged
        self.onContinue = onContinue
        self.onClose = onClose
        _model = State(initialValue: ConnectionsViewModel(
            api: .from(client: client), continueTitle: continueTitle, highlighted: highlighted
        ))
    }

    var body: some View {
        ConnectionsView(state: model.state, actions: model.actions)
            .task { await model.load() }
            .onAppear(perform: wire)
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { model.recheckMonzo() }
            }
            .onReceive(NotificationCenter.default.publisher(for: OnboardingLink.notification)) { note in
                if let url = note.object as? URL { model.handleConnectedURL(url) }
            }
            .onOpenURL { url in model.handleConnectedURL(url) }
            .fileImporter(
                isPresented: $showsPicker,
                allowedContentTypes: [.commaSeparatedText, .pdf, .plainText],
                allowsMultipleSelection: false
            ) { result in
                guard case let .success(urls) = result, let url = urls.first else { return }
                let access = url.startAccessingSecurityScopedResource()
                defer { if access { url.stopAccessingSecurityScopedResource() } }
                guard let data = try? Data(contentsOf: url) else { return }
                let name = url.lastPathComponent
                Task { await model.importStatement(data: data, fileName: name) }
            }
            .llCover(isPresented: $showsNumbers) {
                // Onboarding's form on its own: saving or Back closes it.
                OnboardingScreen(client: client, startAt: .manual) {
                    showsNumbers = false
                    Task { await model.numbersSaved() }
                }
            }
    }

    private func wire() {
        model.pickStatement = { showsPicker = true }
        model.enterNumbers = { showsNumbers = true }
        model.onClose = onClose
        model.onContinue = onContinue
        model.onChanged = onChanged
        // Monzo signs in with an emailed link, so the page opens in Safari (not an in-app browser).
        let open = openURL
        model.openInSafari = { url in open(url) }
    }
}
