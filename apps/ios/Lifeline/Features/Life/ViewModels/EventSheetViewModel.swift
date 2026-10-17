import Foundation
import Observation

/// The open event. The player must pick one choice to continue.
@MainActor
@Observable
final class EventSheetViewModel {
    private let session: GameSession

    init(session: GameSession) {
        self.session = session
    }

    var state: EventSheetViewState? {
        session.activeEvent.map { Self.makeState(event: $0, isSubmitting: session.isBusy) }
    }

    var actions: EventSheetActions {
        EventSheetActions(onChoose: { [weak self] choiceID in
            guard let self, let event = session.activeEvent else { return }
            Task { await self.session.choose(choiceID: choiceID, eventID: event.id) }
        })
    }

    static func makeState(event: LifeEvent, isSubmitting: Bool) -> EventSheetViewState {
        EventSheetViewState(
            id: event.id,
            emoji: event.emoji,
            year: event.year,
            age: event.age,
            title: event.title,
            text: event.text,
            isAIText: event.textSource == .llm,
            choices: event.choices.map {
                .init(id: $0.id, emoji: $0.emoji, label: $0.label, hint: $0.hint, isDefault: $0.isDefault ?? false)
            },
            sources: (event.sources ?? []).map(StateMapping.sourceChip),
            isSubmitting: isSubmitting
        )
    }
}
