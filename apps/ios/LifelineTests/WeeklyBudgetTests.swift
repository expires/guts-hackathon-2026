import Foundation
import Testing
@testable import Lifeline

/// V2 F-R-1: weekly budget moves never show a £ a year figure.
@MainActor
struct WeeklyBudgetTests {
    private func move(_ extra: String, id: String = "mv_week") -> Move {
        ContractExamples.decode("""
        {"id": "\(id)", "kind": "weekly_budget", "action": "Set a weekly budget", "headline": "Your loan arrives on 2 Nov",
         "impact_per_year": 14505, "worst_case_per_year": 9000, "confidence": 0.8, "confidence_label": "x",
         "evidence": [], "sources": [], "options": [], "testable": false, "gain_kind": "weeks_of_cover" \(extra)}
        """)
    }

    @Test func shortfallShowsAmountShortBeforeTheDate() {
        let card = NextMoveViewModel.move(move(#", "shortfall": 676, "deadline": "2026-11-02""#), isInPlan: false)
        #expect(card.impactText == "£676 short before 2 November")
        #expect(!card.impactText.contains("a year"))
        #expect(card.worstCaseText.isEmpty)
    }

    @Test func noShortfallShowsWeeklySpendAndWeeks() {
        let card = NextMoveViewModel.move(move(#", "shortfall": 0, "safe_weekly_spend": 82, "cover_weeks": 3"#), isInPlan: false)
        #expect(card.impactAmountText == "£82")
        #expect(card.impactText == "Spend up to £82 a week. 3 weeks until your next money")
        #expect(!card.impactCaption.contains("a year"))
    }

    @Test func moveLinkHasNoYearlySuffix() {
        let link = MoneyWidgetsViewModel.moveLink(for: .budgets, moves: [move(#", "safe_weekly_spend": 82"#)])
        // weekly_budget is not a budgets kind; check the yearly rule directly too.
        #expect(link == nil || !(link!.text.contains("a year")))
        #expect(!NextMoveViewModel.isYearly(move("")))
    }

    @Test func planTotalExcludesWeeklyBudget() {
        let plan: PlanResponse = ContractExamples.decode("""
        {"items": [
          {"id": "pl_1", "move_id": "mv_week", "kind": "weekly_budget", "action": "Set a weekly budget", "impact_per_year": 14505, "added_at": "2026-10-17T12:00:00Z", "status": "todo"},
          {"id": "pl_2", "move_id": "mv_subs", "kind": "cancel_subscription", "action": "Cancel 2 subscriptions", "impact_per_year": 264, "added_at": "2026-10-17T12:00:00Z", "status": "todo"}],
         "total_impact_per_year": 14769}
        """)
        #expect(NextMoveViewModel.yearlyPlanTotal(plan, moves: [move("")]) == 264)
        #expect(PlanViewModel.makeState(plan: plan, phase: .ready, isSampleData: true).totalPerYear == 264)
    }
}

/// DIRECTION_V2 items W8 found missing (W6 screens).
@MainActor
struct DirectionV2ScreenTests {
    private func move(_ extra: String, kind: String = "weekly_budget", id: String = "mv_week") -> Move {
        ContractExamples.decode("""
        {"id": "\(id)", "kind": "\(kind)", "action": "Set a weekly budget", "headline": "h",
         "impact_per_year": 0, "worst_case_per_year": 0, "confidence": 0.8, "confidence_label": "x",
         "evidence": [], "sources": [], "options": [], "testable": false \(extra)}
        """)
    }

    @Test func weeklyBudgetBlockFromTheMove() {
        let block = MoneyHomeViewModel.weeklyBudget([move(#", "gain_kind": "weeks_of_cover", "safe_weekly_spend": 82, "cover_weeks": 3, "deadline": "2026-11-02""#)])
        #expect(block?.text == "Until 2 November: spend up to £82 a week")
        #expect(block?.detail == "3 weeks until your next money")
        // No safe weekly spend, or no weekly_budget move: no block.
        #expect(MoneyHomeViewModel.weeklyBudget([move(#", "gain_kind": "weeks_of_cover""#)]) == nil)
        #expect(MoneyHomeViewModel.weeklyBudget([move("", kind: "cancel_subscription")]) == nil)
    }

    @Test func whyOpensWithOneSentencePerSourceAndATogetherLine() {
        let move = move(#"""
        , "evidence": [
          {"text": "Your loan arrives on 2 November. That is 3 weeks away.", "facts": {}, "source": {"source": "govuk", "series_id": "loan", "status": "cached"}},
          {"text": "You spend £120 a week on average", "facts": {}, "source": {"source": "bank:sample", "series_id": "s", "status": "mock"}},
          {"text": "A second gov.uk line.", "facts": {}, "source": {"source": "govuk", "series_id": "x", "status": "cached"}}]
        """#)
        let lines = NextMoveWhyViewModel.sourceSentences(move)
        #expect(lines == [
            "gov.uk: Your loan arrives on 2 November.",
            "Your statement: You spend £120 a week on average.",
            NextMoveWhyViewModel.combiningSentence,
        ])
        #expect(NextMoveWhyViewModel.firstSentence("Rate is 4.42% now. More.") == "Rate is 4.42% now.")
    }

    @Test func bankConnectionNoteIsPlainAndComplete() {
        let text = BankConnectionNote.points.joined(separator: " ")
        for word in ["Monzo", "FCA", "GoCardless", "FinanceKit", "statement upload"] {
            #expect(text.contains(word))
        }
        #expect(!text.contains("\u{2014}"))
    }
}
