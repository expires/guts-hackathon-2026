import Foundation
import Testing
@testable import Lifeline

/// ADR 0042/0043: "What you give up", months of cover, links back to the Next Move.
@MainActor
struct TradeOffTests {
    private func move(_ extra: String) -> Move {
        ContractExamples.decode("""
        {"id": "mv_x", "kind": "build_emergency_fund", "action": "Build an emergency fund", "headline": "You have 1 month of costs saved",
         "impact_per_year": 0, "worst_case_per_year": 0, "confidence": 0.8, "confidence_label": "In 8 of 10 cases this helped",
         "evidence": [], "sources": [], "options": [], "testable": false \(extra)}
        """)
    }

    @Test func tradeOffLineAndPoints() {
        let card = NextMoveViewModel.move(move(#", "trade_off": {"summary": "£200 a month less to spend", "points": [{"text": "You spend £200 a month less for 9 months."}]}"#), isInPlan: false)
        #expect(card.tradeOffText == "What you give up: £200 a month less to spend")
        #expect(card.tradeOffPoints == ["You spend £200 a month less for 9 months."])
        let why = NextMoveWhyViewModel.makeState(move: move(#", "trade_off": {"summary": "£200 a month less to spend", "points": [{"text": "A"}, {"text": "B"}]}"#), lesson: nil, lessonPhase: .ready, isSampleData: true)
        #expect(why.tradeOffSummary == "£200 a month less to spend")
        #expect(why.tradeOff.map(\.text) == ["A", "B"])
    }

    @Test func noTradeOffHidesTheLine() {
        #expect(NextMoveViewModel.move(move(""), isInPlan: false).tradeOffText == nil)
    }

    @Test func monthsOfCoverReplacesPoundsAYear() {
        let card = NextMoveViewModel.move(move(#", "gain_kind": "months_of_cover", "cover_months": 4.5"#), isInPlan: false)
        #expect(card.isMonthsOfCover)
        #expect(card.impactAmountText == "4.5 months")
        #expect(card.impactCaption == "of cover")
        #expect(NextMoveViewModel.monthsText(1) == "1 month")
    }

    @Test func guessLinksToTheRealTopMove() {
        let moves = [MockData.recorded.nextMove.top] + MockData.recorded.nextMove.runnersUp
        let link = MoneyWidgetsViewModel.topMoveLink(moves: moves)
        #expect(link?.moveID == moves[0].id)
        #expect(link?.text == "Your next move: \(moves[0].action)")
    }

    @Test func playYourselfPrefillsFromProfileUntilEdited() {
        let model = CharacterFormViewModel(mode: .playYourself)
        #expect(model.state.fields.name.isEmpty)
        let spec = MockData.recorded.financeProfile.character
        model.prefill(spec)
        #expect(model.state.fields.name == spec.name)
        #expect(model.state.fields.town == spec.town)
        var edited = model.state.fields
        edited.name = "Sam"
        model.update(edited)
        model.prefill(spec)
        #expect(model.state.fields.name == "Sam")
    }
}

@MainActor
struct SourceCountTests {
    @Test func basedOnNSourcesFromDecisionSourceCount() {
        var response = MockData.recorded.nextMove
        response.decisionSourceCount = 12
        #expect(NextMoveViewModel.makeState(response: response, phase: .ready).sourceCountText == "Based on 12 sources")
        response.decisionSourceCount = nil
        #expect(NextMoveViewModel.makeState(response: response, phase: .ready).sourceCountText == nil)
        response.decisionSourceCount = 0
        #expect(NextMoveViewModel.makeState(response: response, phase: .ready).sourceCountText == nil)
    }
}
