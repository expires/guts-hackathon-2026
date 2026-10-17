import SwiftUI

/// Glue for the account screen (ADR 0029, 0037). Owns `AccountViewModel`.
struct AccountScreen: View {
    @State private var model: AccountViewModel
    private let onSignedOut: @MainActor () -> Void
    private let onClose: (@MainActor () -> Void)?

    init(client: any LifelineClient, onSignedOut: @escaping @MainActor () -> Void = {}, onClose: (@MainActor () -> Void)? = nil) {
        self.init(api: .from(client: client), isSampleData: client.kind == .mock, onSignedOut: onSignedOut, onClose: onClose)
    }

    init(api: AccountAPI, isSampleData: Bool, onSignedOut: @escaping @MainActor () -> Void = {}, onClose: (@MainActor () -> Void)? = nil) {
        let model = AccountViewModel(api: api, isSampleData: isSampleData)
        model.onClose = onClose
        _model = State(initialValue: model)
        self.onSignedOut = onSignedOut
        self.onClose = onClose
    }

    var body: some View {
        AccountView(state: model.state, actions: model.actions)
            .onAppear { model.onSignedOut = onSignedOut }
            .task { await model.load() }
    }
}
