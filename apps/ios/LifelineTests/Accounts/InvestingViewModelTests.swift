import Foundation
import Testing
@testable import Lifeline

/// Investments and Habits against MockClient.
@MainActor
@Suite("Investments and habits view models")
struct InvestingViewModelTests {
    @Test func investmentsLoadWithSampleLabel() async {
        let model = InvestmentsViewModel(client: MockClient())
        await model.load()
        let state = model.state
        #expect(state.phase == .ready)
        #expect(state.isSampleData)
        #expect(state.dataLabel == "Sample data")
        #expect(state.totalValue == 8_065.85)
        #expect(state.holdings.count == 4)
        #expect(state.slices.first?.label == "Shares")
        #expect(state.replay.dataLabel == "Illustrative returns")
        #expect(state.replay.periods.count == 3)
        #expect(state.replay.mixes.map(\.label) == ["All shares", "80/20", "60/40", "Your current mix"])
    }

    @Test func replayDrawsOneLinePerMixAndExplainsInPlainEnglish() async {
        let model = InvestmentsViewModel(client: MockClient())
        await model.load()
        let replay = model.state.replay
        #expect(replay.phase == .ready)
        #expect(Set(replay.points.map(\.series)).count == 4)
        #expect(replay.results.count == 4)
        #expect(replay.results[0].metrics.map(\.label) == ["Biggest drop", "Back to start after", "Yearly growth"])
        #expect(replay.results[0].metrics[0].value.hasSuffix("% down"))
        #expect(replay.points.filter { $0.month == 0 }.allSatisfy { $0.value > 0 })
    }

    @Test func choicesRerunTheReplay() async {
        let model = InvestmentsViewModel(client: MockClient())
        await model.load()
        model.toggleMix("shares")
        await model.waitForReplay()
        #expect(model.state.replay.results.count == 3)
        model.setMonthly(false)
        await model.waitForReplay()
        #expect(model.state.replay.isMonthly == false)
        model.selectPeriod("covid_2020")
        await model.waitForReplay()
        #expect(model.state.replay.selectedPeriodID == "covid_2020")
        #expect(model.state.paths.basisText.contains("one lump sum"))
    }

    @Test func lastMixCannotBeRemoved() async {
        let model = InvestmentsViewModel(client: MockClient())
        await model.load()
        for id in ["shares", "80-20", "current"] { model.toggleMix(id) }
        await model.waitForReplay()
        model.toggleMix("60-40")
        #expect(model.state.replay.selectedMixIDs == ["60-40"])
    }

    @Test func currentMixWeightsAddUpToOne() {
        let weights = InvestmentsViewModel.currentWeights(SampleInvesting.investments)
        #expect(weights != nil)
        #expect(abs((weights?.values.reduce(0, +) ?? 0) - 1) < 0.0001)
        #expect(weights?["global_equity"] ?? 0 > 0.7)
        var empty = SampleInvesting.investments
        empty.holdings = []
        empty.cash = 0
        #expect(InvestmentsViewModel.currentWeights(empty) == nil)
    }

    @Test func disclaimerIsAlwaysThere() async {
        let model = InvestmentsViewModel(client: MockClient())
        await model.load()
        #expect(model.state.paths.disclaimer == "Modelled scenarios from similar past periods. Not a forecast. Not financial advice.")
        #expect(model.state.paths.points.count == 37)
        #expect(model.state.paths.points.allSatisfy { $0.low <= $0.middle && $0.middle <= $0.high })
        // Even before data arrives the text is there.
        let loading = Fixtures.Investments.loading
        #expect(loading.paths.disclaimer == SampleInvesting.scenarioLabel)
    }

    @Test func habitsShowSevenFactorsAndExplainTheMissingOne() async {
        let model = HabitsViewModel(client: MockClient())
        await model.load()
        let state = model.state
        #expect(state.phase == .ready)
        #expect(state.factors.count == 7)
        #expect(state.overall == 67)
        #expect(state.isSampleData)
        #expect(state.factors[0].label == "Money you keep")
        #expect(state.factors[0].scoreText == "70 out of 100")
        let missing = state.factors.first { $0.score == nil }
        #expect(missing?.reason == "Connect Trading212 to see this.")
        #expect(missing?.scoreText == "Not enough data")
        #expect(state.windowText == "Last 6 months, up to 30 Sep 2026")
    }

    @Test func habitsSampleLabelFollowsMonzo() {
        #expect(HabitsViewModel.isSample(connections: nil, clientKind: .mock))
        #expect(HabitsViewModel.isSample(connections: SampleInvesting.connections(), clientKind: .live))
        let live = SampleInvesting.connections(monzo: SampleInvesting.monzoConnected)
        #expect(!HabitsViewModel.isSample(connections: live, clientKind: .live))
    }

    @Test func contractExamplesDecode() {
        #expect(ContractExamples.connections.providers.count == 2)
        #expect(ContractExamples.investments.holdings.count == 2)
        #expect(ContractExamples.habitFactors.overall == 70)
        #expect(ContractExamples.isaPeriods.periods.first?.id == "gfc_2008")
        #expect(ContractExamples.isaBacktest.results.first?.metrics.maxDrawdown == 0.31)
        #expect(ContractExamples.isaScenarios.fan.p50.count == 3)
    }

    @Test func spreadIsaMoveHasCopy() {
        #expect(MoveKindStyle.title("spread_isa") == "Spread your ISA")
        #expect(MoveKindStyle.systemImage("spread_isa") == "chart.pie")
        #expect(MoneyWidgetsViewModel.Widget.investments.moveKinds == ["spread_isa"])
    }

    @Test func moneyTabSaysLiveOrSample() {
        #expect(Fixtures.MoneyHome.ready.dataStatusText == "Sample data")
        #expect(Fixtures.MoneyHome.connectedLive.dataStatusText == "Live data")
        #expect(Fixtures.MoneyHome.loading.dataStatusText == nil)
        #expect(Fixtures.MoneyHome.ready.connections.anyConnected == false)
        #expect(Fixtures.MoneyHome.connectedLive.connections.anyLive)
    }
}
