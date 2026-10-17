import SwiftUI

/// Glue: owns `EventSheetViewModel` and feeds `EventSheetView`.
struct EventSheetScreen: View {
    @State private var model: EventSheetViewModel
    private let onClose: @MainActor () -> Void
    private let session: GameSession
    @Environment(\.appRoutes) private var routes

    init(session: GameSession, onClose: @escaping @MainActor () -> Void = {}) {
        _model = State(initialValue: EventSheetViewModel(session: session))
        self.session = session
        self.onClose = onClose
    }

    /// The model's actions plus "Not sure? Ask Penny": close the event first, then open Penny from the root.
    private var actions: EventSheetActions {
        var actions = model.actions
        let routes = self.routes
        let close = onClose
        let lifeID = session.life?.id
        let eventID = session.activeEvent?.id
        actions.onAskPenny = {
            close()
            Task { @MainActor in
                try? await Task.sleep(for: .milliseconds(450))
                routes.askPenny(PennyRoute(screen: .lifeEvent, lifeID: lifeID, eventID: eventID))
            }
        }
        return actions
    }

    var body: some View {
        if let state = model.state {
            EventSheetView(state: state, actions: actions)
                .onAppear { model.onClose = onClose }
        }
    }
}
