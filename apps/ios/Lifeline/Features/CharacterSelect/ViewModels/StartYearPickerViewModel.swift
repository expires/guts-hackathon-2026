import Foundation
import Observation

/// Pick the year the life starts. Events then follow real UK data from that year.
@MainActor
@Observable
final class StartYearPickerViewModel {
    let choice: CharacterChoice
    private let session: GameSession
    private(set) var year: Int

    init(choice: CharacterChoice, session: GameSession) {
        self.choice = choice
        self.session = session
        self.year = choice.defaultStartYear
    }

    var state: StartYearPickerViewState {
        Self.makeState(choice: choice, year: year, isStarting: session.isBusy, usesSampleData: session.usesSampleData)
    }

    var actions: StartYearPickerActions {
        StartYearPickerActions(
            onYearChange: { [weak self] in self?.setYear($0) },
            onStart: { [weak self] in Task { await self?.start() } }
        )
    }

    func setYear(_ value: Int) {
        let range = choice.startYearRange
        year = min(range.upperBound, max(range.lowerBound, value))
    }

    @discardableResult
    func start() async -> Bool {
        await session.startLife(choice.request(startYear: year))
    }

    static func makeState(choice: CharacterChoice, year: Int, isStarting: Bool, usesSampleData: Bool) -> StartYearPickerViewState {
        StartYearPickerViewState(
            emoji: choice.character.emoji ?? "🙂",
            name: choice.character.name,
            occupation: choice.character.occupation.capitalized,
            town: choice.character.town,
            birthYear: choice.character.birthYear,
            years: choice.startYearRange,
            selectedYear: year,
            ageAtStart: max(0, year - choice.character.birthYear),
            isStarting: isStarting,
            usesSampleData: usesSampleData
        )
    }
}
