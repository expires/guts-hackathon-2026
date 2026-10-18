import SwiftUI

/// Glue: owns `EventSheetViewModel` and feeds `EventSheetView`.
struct EventSheetScreen: View {
    @State private var model: EventSheetViewModel
    private let onClose: @MainActor () -> Void
    private let session: GameSession
    /// "Not sure? Ask Penny": a Penny sheet over this event (a new chat with the event as context).
    @State private var penny: PennyContext?

    init(session: GameSession, onClose: @escaping @MainActor () -> Void = {}) {
        _model = State(initialValue: EventSheetViewModel(session: session))
        self.session = session
        self.onClose = onClose
    }

    /// The model's actions plus "Not sure? Ask Penny": opens Penny as a sheet over the event.
    /// Closing the sheet returns to the same event.
    private var actions: EventSheetActions {
        var actions = model.actions
        let session = self.session
        let title = model.state?.title ?? ""
        let age = model.state?.age
        let penny = $penny
        actions.onAskPenny = {
            penny.wrappedValue = .lifeEvent(
                lifeID: session.life?.id, eventID: session.activeEvent?.id,
                eventTitle: title, age: age, roomCode: session.life?.roomCode
            )
        }
        return actions
    }

    var body: some View {
        if let state = model.state {
            EventSheetView(state: state, actions: actions)
                .onAppear { model.onClose = onClose }
                .pennySheet($penny, client: session.client)
        }
    }
}
