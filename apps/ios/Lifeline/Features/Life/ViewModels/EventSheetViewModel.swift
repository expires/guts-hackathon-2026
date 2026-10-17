import Foundation
import Observation

/// The open event. The player must pick one choice to continue.
@MainActor
@Observable
final class EventSheetViewModel {
    private let session: GameSession
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(session: GameSession) {
        self.session = session
    }

    var state: EventSheetViewState? {
        session.activeEvent.map { Self.makeState(event: $0, isSubmitting: session.isBusy) }
    }

    var actions: EventSheetActions {
        EventSheetActions(
            onChoose: { [weak self] choiceID in
                guard let self, let event = session.activeEvent else { return }
                Task { await self.session.choose(choiceID: choiceID, eventID: event.id) }
            },
            onClose: { [weak self] in self?.onClose() }
        )
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
            choices: event.choices.map { choice in
                let amount = monthlyPayment(choiceID: choice.id, facts: event.facts?.additionalProperties ?? [:])
                return .init(
                    id: choice.id, emoji: choice.emoji, label: choice.label, hint: choice.hint, isDefault: choice.isDefault ?? false,
                    amountText: amount.map { Money.format($0) }, amountCaption: amount == nil ? nil : "a month"
                )
            },
            sources: (event.sources ?? []).map(StateMapping.sourceChip),
            isSubmitting: isSubmitting,
            area: LifeViewModel.area(event.area.rawValue),
            areaLabel: LifeViewModel.area(event.area.rawValue).capitalized,
            dateText: "\(event.year) · Age \(event.age)"
        )
    }

    /// `pay_2y` for `fix_2y`, `pay_5y` for `fix_5y`, `pay_svr` for `svr`, else `pay_<id>`.
    static func monthlyPayment(choiceID: String, facts: [String: Double]) -> Double? {
        let key = "pay_" + (choiceID.hasPrefix("fix_") ? String(choiceID.dropFirst(4)) : choiceID)
        return facts[key]
    }
}
