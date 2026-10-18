import SwiftUI

/// Glue: owns `PennyViewModel` and feeds `PennyChatView` (ADR 0011, ADR 0031).
///
/// Entry points (Ask Penny context fix). Each one starts a NEW chat and sends its question at once:
/// - Life event and room rounds: `.pennySheet($penny, client:)` (PennySheet.swift) over the event, with
///   `PennyContext.lifeEvent(...)` or `PennyContext.roomRound(...)`.
/// - Next Move ("Why this move?"), Why? ("Explain this simply") and Test it ("What does this result mean?"):
///   `routes.askPenny(PennyRoute(...))` switches to the Penny tab (`PennyTabModel.ask`).
struct PennyScreen: View {
    @State private var model: PennyViewModel
    private let onClose: @MainActor () -> Void
    private let onOpenLink: @MainActor (PennyLink) -> Void
    @Environment(\.llPresentationMode) private var presentation

    /// - Parameters:
    ///   - client: the shared client. Penny streams with `askPennyStream` and falls back to `askPenny`.
    ///   - context: where the chat opened. `context.question` is sent at once.
    ///   - onOpenLink: Penny's link buttons (Next Move, Test it, Why, plan). The caller closes the sheet and routes.
    init(
        client: any LifelineClient,
        context: PennyContext = .init(),
        onClose: @escaping @MainActor () -> Void,
        onOpenLink: @escaping @MainActor (PennyLink) -> Void = { _ in }
    ) {
        self.init(service: .live(client), context: context, onClose: onClose, onOpenLink: onOpenLink)
    }

    /// Tests and the Playground pass a scripted service.
    init(
        service: PennyService,
        context: PennyContext = .init(),
        onClose: @escaping @MainActor () -> Void,
        onOpenLink: @escaping @MainActor (PennyLink) -> Void = { _ in }
    ) {
        _model = State(initialValue: PennyViewModel(service: service, context: context))
        self.onClose = onClose
        self.onOpenLink = onOpenLink
    }

    var body: some View {
        PennyChatView(state: model.state, actions: model.actions)
            .onAppear {
                model.onClose = onClose
                model.onOpenLink = onOpenLink
                model.presentation = presentation
            }
            .onChange(of: presentation) { _, value in model.presentation = value }
            .task { await model.start() }
    }
}
