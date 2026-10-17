import Foundation
import Testing
@testable import Lifeline

/// Real-life Decision screen (ADR 0018 entry points). W7.
@MainActor
@Suite("Real-life Decision ViewModel")
struct RealLifeDecisionViewModelTests {
    @Test func moneyContextLoads() async {
        let model = RealLifeDecisionViewModel(client: MockClient(), profile: ContractExamples.decisionProfile, lifeID: nil)
        #expect(model.context == .money)
        await model.load()
        let state = model.state
        #expect(state.phase == .ready)
        #expect(state.title == "Your real decision")
        #expect(state.headline == "Fix for 5 years.")
        #expect(state.actionID == "fix_5y")
        #expect(state.successText == "7 in 10")
        #expect(state.basisSentence == "Based on 40 similar lives in 1989-1991, 2006-2008 and 2022-2024.")
        #expect(!state.canTestIt)
    }

    @Test func playYourselfContextFromLifeID() async {
        let model = RealLifeDecisionViewModel(client: MockClient(), profile: ContractExamples.decisionProfile, lifeID: "lf_mock01")
        #expect(model.context == .playYourself)
        await model.load()
        #expect(model.state.title == "You reached today")
    }

    @Test func whyMoveOffersTestIt() async {
        let model = RealLifeDecisionViewModel(
            client: MockClient(), profile: ContractExamples.decisionProfile, lifeID: nil,
            context: .whyMove, moveID: "mv_fix_mortgage"
        )
        await model.load()
        #expect(model.state.title == "Why this move?")
        #expect(!model.state.canTestIt, "Hidden until the glue wires onTestIt")
        var tested: [String] = []
        model.onTestIt = { tested.append($0) }
        #expect(model.state.canTestIt)
        model.actions.onTestIt()
        #expect(tested == ["mv_fix_mortgage"])
    }

    @Test func emptyStatesKeepTitle() {
        let loading = RealLifeDecisionViewModel.makeState(
            decision: nil, phase: .loading(.init(message: RealLifeDecisionViewModel.loadingMessage)), context: .whyMove, canTestIt: true
        )
        #expect(loading.title == "Why this move?")
        #expect(!loading.canTestIt)
        #expect(loading.headline.isEmpty)
    }

    @Test func helperText() {
        #expect(RealLifeDecisionViewModel.successText(0.04) == "0 in 10")
        #expect(RealLifeDecisionViewModel.successText(1.4) == "10 in 10")
        #expect(RealLifeDecisionViewModel.basisSentence(twins: 1, periods: []) == "Based on 1 similar life.")
        #expect(RealLifeDecisionViewModel.basisSentence(twins: 12, periods: ["2008-2010"]) == "Based on 12 similar lives in 2008-2010.")
        #expect(RealLifeDecisionViewModel.actionLabel("build_emergency_fund") == "Build Emergency Fund")
    }

    @Test func profileFromCharacter() {
        let character = TestItFixtures.result.character
        let profile = DecisionProfileMapping.profile(
            from: character, currentYear: 2026,
            dealEndsInMonths: DecisionProfileMapping.months(fromDaysLeft: 165)
        )
        #expect(profile.age == 34)
        #expect(profile.region == "yorkshire-and-the-humber")
        #expect(profile.annualIncome == 38_000)
        #expect(profile.savings == 6_200)
        #expect(profile.otherDebt == 0)
        #expect(profile.housing == .mortgage)
        #expect(profile.propertyValue == 240_000)
        #expect(profile.mortgageBalance == 180_000)
        #expect(profile.dealEndsInMonths == 6)
    }

    @Test func profileClampsToContractLimits() {
        var character = TestItFixtures.result.character
        character.birthYear = 2020
        character.annualIncome = -5
        character.housing = nil
        character.propertyValue = 0
        let profile = DecisionProfileMapping.profile(from: character, currentYear: 2026, dealEndsInMonths: 500, mortgageYearsLeft: -1)
        #expect(profile.age == 16)
        #expect(profile.annualIncome == 0)
        #expect(profile.housing == .rent)
        #expect(profile.propertyValue == nil)
        #expect(profile.dealEndsInMonths == 120)
        #expect(profile.mortgageYearsLeft == 0)
        #expect(DecisionProfileMapping.months(fromDaysLeft: 0) == 0)
        #expect(DecisionProfileMapping.months(fromDaysLeft: 30) == 1)
    }
}
