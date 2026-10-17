import Foundation

/// Rewind fixtures for previews and the Playground (W7, ADR 0026). Every state goes through `RewindViewModel`.
@MainActor
enum RewindFixtures {
    /// Mid-life fixture where the newest decision is the 2021 mortgage offer, answered with a 2-year fix.
    static var mortgageLife: Life {
        var life = Fixtures.midLife
        life.year = 2024
        life.age = 42
        life.index.value = 96
        life.history = life.history.filter { $0.year < 2021 } + [
            .init(
                year: 2021, age: 39, text: "My mortgage offer is ready. I fixed for 2 years.",
                decisionId: "ev-2021-1", eventId: "ev-2021-1", choiceId: "fix_2y",
                netWorth: 128_000, autopilotNetWorth: 118_000, index: 104.0
            ),
        ]
        life.rewind.freeLeft = 2
        return life
    }

    static var mortgage: RewindPickerViewState {
        RewindViewModel.makePickerState(life: mortgageLife, hasPass: false, isSubmitting: false, usesSampleData: true)
    }

    /// An older decision with no fixture alternative: plain "other choice" card.
    static var otherDecision: RewindPickerViewState {
        RewindViewModel.makePickerState(
            life: mortgageLife, hasPass: false, isSubmitting: false, selectedID: "ev-2015-2", usesSampleData: true
        )
    }

    static var needsPass: RewindPickerViewState {
        var life = mortgageLife
        life.rewind.freeLeft = 0
        return RewindViewModel.makePickerState(life: life, hasPass: false, isSubmitting: false, usesSampleData: true)
    }

    static var all: [(id: String, title: String, state: RewindPickerViewState)] {
        [
            ("rewind.mortgage", "2021 mortgage, 5-year fix at 1.28%", mortgage),
            ("rewind.other", "Older decision, no fixture", otherDecision),
            ("rewind.mortgagePass", "Needs Rewind Pass", needsPass),
        ]
    }
}
