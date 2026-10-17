import Foundation
import Testing
@testable import Lifeline

/// ADR 0053: bugs from phone testing (W6 screens).
@MainActor
struct PhoneBugTests {
    private func move(_ extra: String) -> Move {
        ContractExamples.decode("""
        {"id": "mv_x", "kind": "build_emergency_fund", "action": "Build a safety fund", "headline": "Keep some cash aside",
         "impact_per_year": 120, "worst_case_per_year": 0, "confidence": 0.9, "confidence_label": "In 9 of 10 cases this helped",
         "evidence": [], "sources": [], "options": [], "testable": false \(extra)}
        """)
    }

    @Test func confidenceShowsLevelAndSampleSize() {
        let high = NextMoveViewModel.move(move(#", "confidence_level": "high", "sample_size": 240"#), isInPlan: false)
        #expect(high.confidenceWord == "High · sample 240")
        #expect(high.confidenceFilled == 3)
        // The engine says low with a small sample, even when the raw confidence is high.
        let low = NextMoveViewModel.move(move(#", "confidence_level": "low", "sample_size": 6"#), isInPlan: false)
        #expect(low.confidenceWord == "Low · sample 6")
        #expect(low.confidenceFilled == 1)
    }

    @Test func monthsOfCoverWithoutCostsAsksForThem() {
        let card = NextMoveViewModel.move(move(#", "gain_kind": "months_of_cover""#), isInPlan: false)
        #expect(card.isGainMissing)
        #expect(card.impactCaption == "Add your monthly costs to see this")
        #expect(!card.impactAmountText.contains("months"))
    }

    @Test func overviewPartsShowTheCalculation() {
        var response = ContractExamples.financeOverview
        response.balanceParts = [.init(label: "Current account you entered", amount: 1186), .init(label: "Savings you entered", amount: 6850)]
        response.netWorthParts = nil
        let overview = MoneyWidgetsViewModel.overview(response)
        #expect(overview.balanceParts.map(\.label) == ["Current account you entered", "Savings you entered"])
        #expect(overview.balanceParts.map(\.amount) == [1186, 6850])
        #expect(overview.netWorthParts.isEmpty)
    }

    @Test func noGuessHistoryNoInventedStreak() {
        let state = GuessSpendViewModel.makeState(prediction: ContractExamples.spendPredictionBeforeGuess, guesses: nil, phase: .ready, today: nil)
        #expect(state.streakText.isEmpty)
    }

    @Test func noPaydayWithoutDaysToPayday() {
        var prediction = ContractExamples.spendPredictionBeforeGuess
        prediction.daysToPayday = nil
        #expect(prediction.daysToPayday.map(MoneyHomeViewModel.paydayText) == nil)
    }

    @Test func chosenEventChoiceIsMarked() {
        let state = Fixtures.Event.chosen
        #expect(state.chosenID == state.choices.first?.id)
        #expect(Fixtures.Event.rentRise.chosenID == nil)
    }
}

/// Feature map fixes (W6 screens).
@MainActor
struct FeatureMapFixTests {
    @Test func sampleStatementBadgeSaysSampleData() {
        let sample: FinanceMeta = ContractExamples.decode(#"{"data_status": "mock", "source": "sample", "as_of": "2026-10-16", "label": "Sample data"}"#)
        let mock: FinanceMeta = ContractExamples.decode(#"{"data_status": "mock", "source": "fixtures", "as_of": "2026-10-16"}"#)
        let live: FinanceMeta = ContractExamples.decode(#"{"data_status": "live", "source": "manual", "as_of": "2026-10-16"}"#)
        #expect(FinanceMapping.badgeText(sample) == "Sample data")
        #expect(FinanceMapping.badgeText(mock) == "Mock data")
        #expect(FinanceMapping.badgeText(live) == nil)
    }

    @Test func whyConfidenceMatchesTheCard() {
        let move: Move = ContractExamples.decode("""
        {"id": "mv_x", "kind": "cancel_subscription", "action": "Cut 2 subscriptions", "headline": "h", "impact_per_year": 120,
         "worst_case_per_year": 0, "confidence": 0.9, "confidence_label": "x", "evidence": [], "sources": [], "options": [],
         "testable": false, "confidence_level": "medium", "sample_size": 40}
        """)
        let why = NextMoveWhyViewModel.makeState(move: move, lesson: nil, lessonPhase: .ready, isSampleData: true)
        #expect(why.confidenceChip == "Medium")
        #expect(NextMoveViewModel.move(move, isInPlan: false).confidenceWord.hasPrefix("Medium"))
    }

    @Test func playYourselfUsesProfileAge() {
        let profile: FinanceProfile = ContractExamples.decode("""
        {"meta": {"data_status": "mock", "source": "sample", "as_of": "2026-10-16", "label": "Sample data"},
         "profile": {"age": 19, "region": "north-west", "annual_income": 5040.0, "savings": 330.0, "other_debt": 0.0, "housing": "rent"},
         "character": {"name": "You", "occupation": "Student", "region": "north-west", "town": "Manchester", "birth_year": 1991, "annual_income": 0.0},
         "personal_facts": [], "is_student": true}
        """)
        let model = CharacterFormViewModel(mode: .playYourself)
        let now = FinanceMapping.date("2026-10-17")!
        model.prefill(profile: profile, now: now)
        #expect(model.state.fields.birthYear == 2007)
        #expect(model.state.fields.income == 5040)
        #expect(model.state.fields.town == "Manchester")
        #expect(!model.state.showsBankConnect)
    }
}

/// V4 Direction V2 steps 1-3 (W6).
@MainActor
struct V4StepThreeTests {
    @Test func noConfidenceWithoutEngineLevel() {
        let move: Move = ContractExamples.decode("""
        {"id": "mv_f", "kind": "cancel_subscription", "action": "Cut 2 subscriptions", "headline": "h", "impact_per_year": 120,
         "worst_case_per_year": 0, "confidence": 0.2, "confidence_label": "x", "evidence": [], "sources": [], "options": [], "testable": false}
        """)
        let card = NextMoveViewModel.move(move, isInPlan: false)
        #expect(card.confidenceWord.isEmpty)
        #expect(card.confidenceFilled == 0)
        #expect(NextMoveWhyViewModel.makeState(move: move, lesson: nil, lessonPhase: .ready, isSampleData: true).confidenceChip.isEmpty)
    }

    @Test func sourcesUseHumanNames() {
        let refs: [SourceRef] = ContractExamples.decode("""
        [{"source": "bank:sample", "series_id": "scholarship", "status": "mock", "note": "Sample data"},
         {"source": "govuk", "series_id": "student_finance", "status": "cached"},
         {"source": "boe", "series_id": "IUMBV42", "status": "live"}]
        """)
        let line = NextMoveWhyViewModel.sourcesLine(refs)
        #expect(line == "Your statement · sample data, gov.uk · saved copy, Bank of England · live")
        #expect(!(line ?? "").contains("bank:"))
    }
}
