import Foundation

/// Life summary fixtures for previews and the Playground (W7, ADR 0026). Mock data, labelled on screen.
@MainActor
enum SummaryFixtures {
    static var fourRibbonsSummary: LifeSummary {
        var summary = ContractExamples.summary
        summary.timeline = Fixtures.midLife.history + [
            .init(year: 2040, age: 58, text: "Paid off the mortgage.", netWorth: 268_000, autopilotNetWorth: 212_000, index: 116),
            .init(year: 2061, age: 79, text: "Died of old age.", netWorth: 312_000, autopilotNetWorth: 241_000, index: 118.5),
        ]
        summary.keyMoments = [
            .init(year: 2015, age: 33, emoji: "🏡", text: "Bought a home in Headingley"),
            .init(year: 2022, age: 40, emoji: "📈", text: "Fixed for 5 years"),
            .init(year: 2040, age: 58, emoji: "🎉", text: "Paid off the mortgage"),
        ]
        summary.ribbons += [
            .init(id: "saver", title: "Super Saver", emoji: "🐖", reason: "Saved 10% of pay for 20 years"),
            .init(id: "debtfree", title: "Debt free at 58", emoji: "🎉", reason: "Mortgage paid off in 2040"),
            .init(id: "nurse", title: "Nurse for 38 years", emoji: "🩺", reason: "Same job from 2006 to 2044"),
        ]
        return summary
    }

    static var fourRibbons: LifeSummaryViewState {
        LifeSummaryViewModel.makeState(summary: fourRibbonsSummary, emoji: "👩🏽‍⚕️", phase: .ready, usesSampleData: true)
    }

    static var all: [(id: String, title: String, state: LifeSummaryViewState)] {
        [("summary.fourRibbons", "Four ribbons, mock data", fourRibbons)]
    }
}
