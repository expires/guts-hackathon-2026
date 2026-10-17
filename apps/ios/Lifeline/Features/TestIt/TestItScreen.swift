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

    var body: some View {
        TestItView(state: model.state, actions: model.actions)
            .onAppear {
                model.onOpenLife = onOpenLife
                model.onClose = onClose
                model.onDoThis = onDoThis
            }
            .task { await model.load() }
    }
}
