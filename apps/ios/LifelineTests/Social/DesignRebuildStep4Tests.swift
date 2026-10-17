import Foundation
import Testing
@testable import Lifeline

/// ADR 0026 step 4 (W7): Test it, Lesson, Rewind and Summary mappings. Every number comes from fixtures or the API.
@MainActor
@Suite("Design rebuild step 4")
struct DesignRebuildStep4Tests {
    @Test func testItHeroAndYearRows() throws {
        let state = TestItFixtures.ready
        let hero = try #require(state.hero)
        // 41,980 - 37,800 = 4,180 less paid with the recommended option.
        // Recommended 37,800 against the cheapest other option 41,980.
        #expect(hero.amount == 4_180)
        #expect(hero.amountText == "£4,180")
        #expect(hero.caption == "less paid than \"Fix for 2 years\"")
        #expect(hero.text == state.summary)
        #expect(state.intro == "Two of you. Same life. One choice is different.")
        let rows = state.options[0].yearRows
        // Born 1992: 2021 is age 29.
        #expect(rows.map(\.title) == ["2021 · Age 29", "2022 · Age 30", "2023 · Age 31"])
        #expect(rows[1].change == "Up £5,200")
        #expect(state.options[0].costLabel == "Paid from 2021 to 2023")
        #expect(TestItFixtures.single.hero == nil)
        #expect(!state.canDoThis)
    }

    @Test func recordedTestNextMoveDecodes() throws {
        // MockData.recorded drops a file that fails to decode and falls back to the contract example
        // (the old "£4,180" hero). Decode the file here without `try?`, so a schema drift fails the test.
        let url = try #require(Bundle.main.url(forResource: "testNextMove", withExtension: "json"))
        let result = try ContractExamples.decoder.decode(Components.Schemas.TestMoveResult.self, from: Data(contentsOf: url))
        #expect(result.moveId == "fix_mortgage")
        #expect(MockData.recorded.testMoveResult.summary == result.summary)
    }

    @Test func testItHeroMatchesRecordedMock() async throws {
        // Recorded/testNextMove.json, served by MockClient in the Mock build.
        let client = MockClient(data: .recorded)
        let result = try await client.testNextMove(moveID: "fix_mortgage", optionIDs: nil)
        let state = TestItViewModel.makeState(result: result, phase: .ready)
        let hero = try #require(state.hero)
        let best = try #require(state.recommended)
        let other = try #require(state.options.filter { $0.id != best.id }.min { $0.totalCost < $1.totalCost })
        // Recorded engine output: tracker £33,245.46 against fix_2y £25,965.90.
        #expect(best.id == "tracker")
        #expect(other.id == "fix_2y")
        #expect(hero.amount == abs(best.totalCost - other.totalCost).rounded())
        #expect(hero.amountText == "£7,280")
        #expect(hero.caption == "more paid than \"Fix for 2 years\"")
        // The sentence is the API summary, verbatim, and its £ figure equals the computed hero amount.
        #expect(hero.text == result.summary)
        #expect(hero.text.contains(hero.amountText))
        #expect(state == TestItFixtures.recorded)
        #expect(!hero.text.contains("4,180"))
    }

    @Test func testItDoThisPassesMoveID() {
        let model = TestItViewModel(moveID: "mv_fix_mortgage", load: TestItFixtures.mockLoader)
        var added: [String] = []
        model.onDoThis = { added.append($0) }
        #expect(model.state.canDoThis)
        model.actions.onDoThis()
        #expect(added == ["mv_fix_mortgage"])
    }

    @Test func lessonHeroComesFromTheChart() {
        let state = LessonFixtures.rateShock
        #expect(state.heroLine == "£695 → £1,150")
        #expect(state.changeSentence == "Up £455 from Sep 2021 to Sep 2023.")
        #expect(state.eyebrow == "2023 · Age 31")
        #expect(state.canRewind)
        let plain = Fixtures.LessonScreen.unanswered
        #expect(plain.heroLine == "3.2% → 4.1%")
        #expect(plain.changeSentence == "Up 0.9 points from 2006 to 2008.")
        #expect(plain.eyebrow == nil)
        #expect(!plain.canRewind)
    }

    @Test func rewindUsesTheFixtureRate() throws {
        let state = RewindFixtures.mortgage
        #expect(state.selectedID == "ev-2021-1")
        let alt = try #require(state.alternative)
        #expect(alt.title == "Fix for 5 years")
        #expect(alt.lines.first == "Rate 1.28%")
        #expect(alt.source?.id == "boe.IUMBV42")
        #expect(alt.source?.status == .mock)
        // No payment in the fixture, so no payment line. The app never calculates one.
        #expect(alt.lines == ["Rate 1.28%", "Next choice: 2026"])
        #expect(state.indexGapText == "4 behind")
        #expect(state.isBehind)
        #expect(state.timeline.last == "Now")
        #expect(RewindFixtures.otherDecision.alternative?.source == nil)
        #expect(alt.sources.map(\.id) == ["boe.IUMBV42"])
        #expect(alt.sources.first?.name == "BoE IUMBV42, Sep 2021")
    }

    @Test func rewindShowsAPaymentOnlyWithItsSource() throws {
        let option = RewindPickerViewState.Option(
            id: "ev-2021-1", year: 2021, age: 39, text: "Fixed for 2 years", netWorth: 0, index: 100, choiceID: "fix_2y"
        )
        let paymentSource = SourceChipState(id: "test.payment", name: "Test lender table", status: .mock, note: nil)
        var withPayment = RewindAlternatives.fiveYearFix2021
        withPayment.monthlyPayment = SourcedAmount(amount: 700, source: paymentSource)
        let shown = RewindViewModel.alternative(option, table: ["fix_2y": withPayment])
        #expect(shown.lines == ["Rate 1.28%", "2021: £700 a month", "Next choice: 2026"])
        #expect(shown.sources.map(\.id) == ["boe.IUMBV42", "test.payment"])
        let plain = RewindViewModel.alternative(option)
        #expect(!plain.lines.contains { $0.contains("a month") })
        #expect(plain.paymentSource == nil)
    }

    @Test func summaryIndexSentenceAndDeltas() {
        let state = SummaryFixtures.fourRibbons
        #expect(state.indexText == "119")
        #expect(state.indexSentence == "19 points ahead of your autopilot twin.")
        #expect(state.title == "Amira's life")
        #expect(state.lifespanText == "1982 to 2061 · lived to 79")
        #expect(state.ribbons.count == 4)
        // 2015: 101.4 to 106.0.
        #expect(state.keyMoments[0].indexDelta == "+5")
        #expect(state.shareText.contains("INDEX 119"))
    }
}
