import SwiftUI

/// Penny as a full tab (ADR 0051, DIRECTION_V2 section 6). One chat per app session.
///
/// The app creates one `PennyTabModel` and keeps it for the session (for example as `@State` in RootScreen):
/// ```swift
/// @State private var penny = PennyTabModel(client: session.client)
/// ...
/// PennyTab(model: penny, onOpenLink: { link in /* route */ })   // the Penny tab
/// // routes.askPenny(context): select the Penny tab, then
/// penny.ask(context)
/// ```
@MainActor
@Observable
final class PennyTabModel {
    let chat: PennyViewModel

    convenience init(client: any LifelineClient) {
        self.init(service: .live(client))
    }

    init(service: PennyService) {
        chat = PennyViewModel(service: service)
        chat.isTab = true
    }

    /// "Ask Penny" from Money, Why?, a Life event or the Next Move card: loads the context into this chat
    /// and sends its question, if any.
    func ask(_ context: PennyContext) {
        chat.ask(context)
    }
}

/// Glue for the Penny tab: the chat with no close button, on the paper background.
struct PennyTab: View {
    let model: PennyTabModel
    var onOpenLink: @MainActor (PennyLink) -> Void = { _ in }
    @Environment(\.llPresentationMode) private var presentation

    var body: some View {
        PennyChatView(state: model.chat.state, actions: model.chat.actions)
            .paperBackground()
            .onAppear {
                model.chat.onOpenLink = onOpenLink
                model.chat.presentation = presentation
            }
            .task { await model.chat.start() }
    }
}
