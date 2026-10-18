import SwiftUI

/// Glue: owns `TestItViewModel` and feeds `TestItView` (ADR 0011, ADR 0018).
///
/// The Next Move card (W6) presents it, usually as a sheet:
/// ```swift
/// TestItScreen(
///     moveId: move.id,
///     load: { moveID, optionIDs in try await client.testNextMove(moveID: moveID, optionIDs: optionIDs) },
///     onOpenLife: { lifeID in /* open the stored life in the Life tab */ },
///     onClose: { sheet = nil }
/// )
/// ```
struct TestItScreen: View {
    @State private var model: TestItViewModel
    @Environment(\.llPresentationMode) private var presentation
    private let onOpenLife: @MainActor (String) -> Void
    private let onClose: @MainActor () -> Void
    private let onDoThis: (@MainActor (String) -> Void)?

    /// - Parameters:
    ///   - moveId: `Move.id` from `GET /v1/next-move`.
    ///   - optionIDs: nil tests every option of the move (API default).
    ///   - load: calls `POST /v1/next-move/test`.
    ///   - onDoThis: called with the move id when the player taps "Do this". Nil hides the button.
    ///   - onOpenLife: called with `OptionOutcome.life_id` when the player taps "Open in Life".
    init(
        moveId: String,
        optionIDs: [String]? = nil,
        load: @escaping TestItLoader,
        onOpenLife: @escaping @MainActor (String) -> Void = { _ in },
        onClose: @escaping @MainActor () -> Void = {},
        onDoThis: (@MainActor (String) -> Void)? = nil
    ) {
        let model = TestItViewModel(moveID: moveId, optionIDs: optionIDs, load: load)
        model.onDoThis = onDoThis
        _model = State(initialValue: model)
        self.onOpenLife = onOpenLife
        self.onClose = onClose
        self.onDoThis = onDoThis
    }

    @Environment(\.appRoutes) private var routes

    /// The model's actions plus "Ask Penny what this means": close Test it, then switch to the Penny tab
    /// with a new chat about this result.
    private var actions: TestItActions {
        var actions = model.actions
        let routes = self.routes
        let close = onClose
        let moveID = model.moveID
        let title = model.state.title
        actions.onAskPenny = {
            close()
            Task { @MainActor in
                try? await Task.sleep(for: .milliseconds(450))
                routes.askPenny(PennyRoute(screen: .testIt, nextMoveID: moveID, question: PennyQuestion.testIt, title: String(title.prefix(80))))
            }
        }
        return actions
    }

    var body: some View {
        TestItView(state: model.state, actions: actions)
            .onAppear {
                model.onOpenLife = onOpenLife
                model.onClose = onClose
                model.onDoThis = onDoThis
                model.presentation = presentation
            }
            .onChange(of: presentation) { _, value in model.presentation = value }
            .task { await model.load() }
    }
}
