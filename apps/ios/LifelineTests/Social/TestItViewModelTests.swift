import Foundation
import Testing
@testable import Lifeline

/// "Test it" comparison (ADR 0018). W7.
@MainActor
@Suite("Test it ViewModel")
struct TestItViewModelTests {
    @Test func loadsContractExample() async throws {
        let model = TestItViewModel(moveID: "mv_fix_mortgage", load: TestItFixtures.mockLoader)
        #expect(model.state.phase.isLoading)
        await model.load()
        let state = model.state
        #expect(state.phase == .ready)
        #expect(state.periodLabel == "2021-2023 rate shock")
        #expect(state.periodSentence == "We played your money through 2021 to 2023.")
        #expect(state.options.map(\.id) == ["fix_5y", "fix_2y"])
        #expect(state.recommendedID == "fix_5y")
        #expect(state.summary == "Fixing for 5 years left you £4,180 better off by 2023.")
        #expect(state.evidenceSentence == "7 in 10 twins in similar past periods did better.")
        #expect(state.sources.count == 3)
        #expect(state.sources.allSatisfy { $0.status == .live })
        #expect(!state.isSampleData)
    }

    @Test func optionNumbersComeFromTheAPI() throws {
        let state = TestItFixtures.ready
        let best = try #require(state.recommended)
        #expect(best.lifeID == "lf_t5y001")
        #expect(best.endNetWorth == 77_900)
        #expect(best.totalCost == 37_800)
        #expect(best.missedPayments == 0)
        #expect(best.worstYear == 2022)
        #expect(best.worstYearChange == 5_200)
        #expect(best.index == 104.2)
        #expect(best.path.map(\.year) == [2021, 2022, 2023])
        #expect(best.startNetWorth == 66_000)
        // 77,900 - 73,720 = 4,180, the same gap as the API summary.
        #expect(best.endNetWorthGap == 4_180)
        #expect(state.options[1].endNetWorthGap == -4_180)
        #expect(best.facts == [
            "Ended with £77,900",
            "Paid £37,800",
            "No missed payments",
            "Worst year 2022: +£5,200",
            "Index 104.2",
        ])
        #expect(best.accessibilitySummary.hasPrefix("Fix for 5 years. Recommended. Ended with £77,900"))
        #expect(best.accessibilitySummary.hasSuffix("£4,180 ahead of the next best"))
    }

    @Test func chartRangeIsSharedAndPadded() {
        let state = TestItFixtures.ready
        // Values 66,000 to 77,900, span 11,900, 10% pad 1,190.
        #expect(abs(state.chartMin - 64_810) < 0.001)
        #expect(abs(state.chartMax - 79_090) < 0.001)
        #expect(TestItViewModel.chartRange([]) == (0, 1))
        #expect(TestItViewModel.chartRange([100, 100]) == (90, 110))
    }

    @Test func sampleSourcesSetTheBadge() {
        let state = TestItFixtures.sampleData
        #expect(state.isSampleData)
        #expect(state.options.count == 3)
        #expect(state.options[2].facts.contains("2 missed payments"))
        #expect(TestItFixtures.mixed.sources.map(\.status) == [.live, .cached, .mock])
    }

    @Test func singleOptionHasNoGap() {
        let state = TestItFixtures.single
        #expect(state.options.count == 1)
        #expect(state.options[0].endNetWorthGap == nil)
    }

    @Test func passesMoveAndOptionIDs() async {
        let recorder = CallRecorder()
        let model = TestItViewModel(moveID: "mv_fix_mortgage", optionIDs: ["fix_2y"]) { moveID, optionIDs in
            await recorder.record(moveID: moveID, optionIDs: optionIDs)
            return try await TestItFixtures.mockLoader(moveID, optionIDs)
        }
        await model.load()
        #expect(await recorder.calls == [Call(moveID: "mv_fix_mortgage", optionIDs: ["fix_2y"])])
        #expect(model.state.options.map(\.id) == ["fix_2y"])
        #expect(model.state.recommendedID == nil)
    }

    @Test func offlineShowsErrorThenRetryRecovers() async {
        let flaky = FlakyLoader()
        let model = TestItViewModel(moveID: "mv_fix_mortgage") { moveID, optionIDs in
            try await flaky.load(moveID, optionIDs)
        }
        await model.load()
        guard case let .failed(error) = model.state.phase else {
            Issue.record("Expected an error phase")
            return
        }
        #expect(error.title == "You are offline")
        #expect(error.canRetry)
        #expect(model.state.options.isEmpty)
        await model.load()
        #expect(model.state.phase == .ready)
        #expect(model.state.options.count == 2)
    }

    @Test func serverErrorUsesAPIMessage() async {
        let model = TestItViewModel(moveID: "mv_x") { _, _ in
            throw APIError.server(status: 404, code: "not_found", message: "Move mv_x not found.", source: "api")
        }
        await model.load()
        #expect(model.state.phase == TestItFixtures.notFound.phase)
    }

    @Test func emptyOutcomesIsAnError() async {
        let model = TestItViewModel(moveID: "mv_fix_mortgage") { _, _ in
            var value = await TestItFixtures.result
            value.outcomes = []
            return value
        }
        await model.load()
        #expect(model.state.phase == .failed(TestItViewModel.emptyError))
    }

    @Test func openInLifePassesLifeID() {
        let model = TestItViewModel(moveID: "mv_fix_mortgage", load: TestItFixtures.mockLoader)
        var opened: [String] = []
        var closed = false
        model.onOpenLife = { opened.append($0) }
        model.onClose = { closed = true }
        model.actions.onOpenLife("lf_t2y001")
        model.actions.onClose()
        #expect(opened == ["lf_t2y001"])
        #expect(closed)
    }

    @Test func badPathDatesAreDropped() {
        #expect(TestItViewModel.pathPoint(.init(date: "2022-12-31", value: 1))?.year == 2022)
        #expect(TestItViewModel.pathPoint(.init(date: "bad", value: 1)) == nil)
    }

    @Test func textHelpers() {
        #expect(TestItViewModel.missedPaymentsText(1) == "1 missed payment")
        #expect(TestItViewModel.gapSentence(0.2) == "Same as the other option")
        #expect(TestItViewModel.gapSentence(-500) == "£500 behind the best")
        #expect(TestItViewModel.periodSentence(start: 2008, end: 2008) == "We played your money through 2008.")
        #expect(TestItFixtures.all.count == 7)
    }
}

private struct Call: Equatable, Sendable {
    var moveID: String
    var optionIDs: [String]?
}

private actor CallRecorder {
    private(set) var calls: [Call] = []
    func record(moveID: String, optionIDs: [String]?) { calls.append(.init(moveID: moveID, optionIDs: optionIDs)) }
}

/// Fails the first call with a network error, then returns the contract example.
private actor FlakyLoader {
    private var count = 0
    func load(_ moveID: String, _ optionIDs: [String]?) async throws -> Components.Schemas.TestMoveResult {
        count += 1
        if count == 1 { throw APIError.network }
        return try await TestItFixtures.mockLoader(moveID, optionIDs)
    }
}
