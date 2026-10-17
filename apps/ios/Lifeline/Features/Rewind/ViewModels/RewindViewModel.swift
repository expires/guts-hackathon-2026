import Foundation
import Observation

/// Rewind: pick a past decision, go back, take the other path.
@MainActor
@Observable
final class RewindViewModel {
    private let session: GameSession
    private(set) var result: RewindResultViewState?
    @ObservationIgnored var onClose: @MainActor () -> Void = {}
    @ObservationIgnored var onBuyPass: @MainActor () -> Void = {}

    init(session: GameSession) {
        self.session = session
    }

    var pickerState: RewindPickerViewState {
        guard let life = session.life else {
            return RewindPickerViewState(options: [], allowanceText: "", needsPass: false, isSubmitting: false)
        }
        return Self.makePickerState(life: life, hasPass: session.hasRewindPass, isSubmitting: session.isBusy)
    }

    var actions: RewindActions {
        RewindActions(
            onPick: { [weak self] id in Task { await self?.rewind(to: id) } },
            onBuyPass: { [weak self] in self?.onBuyPass() },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    func rewind(to decisionID: String) async {
        guard let result = await session.rewind(decisionID: decisionID) else { return }
        self.result = Self.makeResultState(result)
    }

    static func makePickerState(life: Life, hasPass: Bool, isSubmitting: Bool) -> RewindPickerViewState {
        let options = life.history.compactMap { entry -> RewindPickerViewState.Option? in
            guard let id = entry.decisionId else { return nil }
            return .init(id: id, year: entry.year, age: entry.age, text: entry.text, netWorth: entry.netWorth, index: entry.index)
        }
        let pass = hasPass || life.rewind.hasPass == true
        let allowance: String
        if pass {
            allowance = "Rewind Pass: unlimited rewinds"
        } else if life.rewind.freeLeft == 1 {
            allowance = "1 free rewind left"
        } else {
            allowance = "\(life.rewind.freeLeft) free rewinds left"
        }
        return RewindPickerViewState(
            options: options.reversed(),
            allowanceText: allowance,
            needsPass: !pass && life.rewind.freeLeft <= 0,
            isSubmitting: isSubmitting
        )
    }

    static func makeResultState(_ result: RewindResult) -> RewindResultViewState {
        RewindResultViewState(
            year: result.life.year,
            age: result.life.age,
            abandonedIndex: result.abandonedIndex,
            newIndex: result.life.index.value,
            abandonedNetWorth: result.abandonedNetWorth,
            newNetWorth: result.life.finances.netWorth,
            message: "You are back in \(String(result.life.year)), age \(result.life.age). Choose again."
        )
    }
}
