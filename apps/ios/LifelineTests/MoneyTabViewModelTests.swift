import Foundation
import Testing
@testable import Lifeline

/// Money tab, Next Move, Guess my spend, Play and You ViewModels against MockClient (ADR 0016, 0017, 0018).
@MainActor
@Suite("Money tab ViewModels with MockClient")
struct MoneyTabViewModelTests {
    // MARK: Next Move

    @Test func nextMoveCardShowsContractExample() async throws {
        let model = NextMoveViewModel(client: MockClient())
        await model.load()
        let state = model.state
        #expect(state.phase == .ready)
        #expect(state.question == "What is my next money move?")
        let top = try #require(state.top)
        #expect(top.action == "Fix for 5 years")
        #expect(top.headline == "Your deal ends in 165 days")
        #expect(top.impactPerYear == 1240)
        #expect(top.impactText == "£1,240 a year better off")
        #expect(top.worstCaseText == "Worst past period: £310 a year worse off")
        #expect(top.confidenceLabel == "7 in 10 twins in similar past periods did better")
        #expect(top.deadlineText == "Decide by 31 Mar 2027 (165 days left)")
        #expect(top.sources.count == 3)
        #expect(top.sources.allSatisfy { $0.status == .live })
        #expect(top.isTestable)
        #expect(top.hasLesson)
        #expect(!top.isInPlan)
        #expect(state.runnersUp.map(\.id) == ["mv_cancel_subs"])
        #expect(state.runnersUp[0].deadlineText == nil)
        #expect(state.isSampleData)
        #expect(state.backtestText == "Tested on 58 past cases: right 69% of the time. Always fix for 2 years: 41%.")
    }

    @Test func doThisAddsToPlanOnce() async throws {
        let client = MockClient()
        let model = NextMoveViewModel(client: client)
        await model.load()
        await model.addToPlan(moveID: "mv_fix_mortgage")
        #expect(model.state.top?.isInPlan == true)
        #expect(model.state.planMessage == "Added to your plan. Your plan is worth £1,240 a year.")
        await model.addToPlan(moveID: "mv_fix_mortgage")
        let plan = try await client.plan()
        #expect(plan.items.count == 1)
        #expect(plan.totalImpactPerYear == 1240)
    }

    @Test func doThisUnknownMoveIsIgnored() async throws {
        let client = MockClient()
        let model = NextMoveViewModel(client: client)
        await model.load()
        await model.addToPlan(moveID: "mv_nope")
        #expect(try await client.plan().items.isEmpty)
    }

    @Test func buttonsRouteWithMoveIDs() async {
        let model = NextMoveViewModel(client: MockClient())
        await model.load()
        var testedID: String?
        var whyID: String?
        model.onTestIt = { testedID = $0 }
        model.onWhy = { whyID = $0.id }
        model.actions.onTestIt("mv_fix_mortgage")
        model.actions.onWhy("mv_fix_mortgage")
        #expect(testedID == "mv_fix_mortgage")
        #expect(whyID == "mv_fix_mortgage")
        testedID = nil
        model.actions.onTestIt("mv_cancel_subs")
        #expect(testedID == nil, "The runner-up is not testable")
    }

    @Test func focusShowsRunnerUpAndBack() async {
        let model = NextMoveViewModel(client: MockClient())
        await model.load()
        model.focus("mv_cancel_subs")
        #expect(model.state.displayedMove?.id == "mv_cancel_subs")
        model.focus("mv_fix_mortgage")
        #expect(model.state.focusedMoveID == nil)
        model.focus("unknown")
        #expect(model.state.displayedMove?.id == "mv_fix_mortgage")
    }

    @Test func impactAndDeadlineText() {
        #expect(NextMoveViewModel.impactText(0.4) == "No change a year")
        #expect(NextMoveViewModel.deadlineText(deadline: nil, daysLeft: 1) == "1 day left")
        #expect(NextMoveViewModel.deadlineText(deadline: nil, daysLeft: nil) == nil)
    }

    @Test func testItReturnsContractComparison() async throws {
        let result = try await MockClient().testNextMove(moveID: "mv_fix_mortgage", optionIDs: nil)
        #expect(result.outcomes.map(\.optionId) == ["fix_5y", "fix_2y"])
        let one = try await MockClient().testNextMove(moveID: "mv_fix_mortgage", optionIDs: ["fix_2y"])
        #expect(one.outcomes.map(\.optionId) == ["fix_2y"])
    }

    // MARK: Why?

    @Test func whyShowsThreeEvidencePointsAndLesson() async throws {
        let move = ContractExamples.nextMove.top
        let model = NextMoveWhyViewModel(client: MockClient(), move: move, isSampleData: true)
        await model.load()
        let state = model.state
        #expect(state.evidence.count == 3)
        #expect(state.evidence[0].text == "5-year fixes are 4.21% today, 2-year fixes 4.38%.")
        #expect(state.evidence[0].source?.name == "Bank of England")
        #expect(state.evidence[2].source == nil)
        #expect(state.lessonPhase == .ready)
        let lesson = try #require(state.lesson, "Contract concepts include fixed-vs-variable")
        #expect(lesson.sentences.count == 2)
        #expect(state.hasDecisionDetail)
        model.actions.onOpenLesson()
        #expect(model.presentedLesson?.conceptId == "fixed-vs-variable")
    }

    @Test func whySubscriptionsLessonHasPersonalSentence() async throws {
        let move = ContractExamples.nextMove.runnersUp[0]
        let model = NextMoveWhyViewModel(client: MockClient(), move: move, isSampleData: true)
        await model.load()
        let lesson = try #require(model.state.lesson)
        let expected = try #require(ContractExamples.financeProfile.personalFacts.first { $0.conceptId == "subscriptions" }?.text)
        let personal = try #require(lesson.personal)
        #expect(!personal.isEmpty)
        #expect(personal == expected || ContractExamples.concepts.contains { $0.lesson.personal == personal })
        #expect(!model.state.hasDecisionDetail)
    }

    @Test func lessonStateCarriesPersonalSentence() {
        var lesson = ContractExamples.lesson
        lesson.personal = "You spend £47 a month on 6 subscriptions."
        let state = LessonViewModel.makeState(lesson: lesson, isNewConcept: false, selectedIndex: nil)
        #expect(state.personal == "You spend £47 a month on 6 subscriptions.")
    }

    // MARK: Plan

    @Test func planEmptyThenOneItem() async throws {
        let client = MockClient()
        let model = PlanViewModel(client: client)
        await model.load()
        #expect(model.state.items.isEmpty)
        _ = try await client.addPlanItem(moveID: "mv_fix_mortgage")
        await model.load()
        #expect(model.state.items.map(\.action) == ["Fix for 5 years"])
        #expect(model.state.totalText == "Your plan is worth £1,240 a year.")
        #expect(model.state.items[0].addedText == "Added 17 Oct 2026")
    }

    // MARK: Widgets

    @Test func widgetsLoadContractExamplesWithMoveLinks() async throws {
        let home = MoneyHomeViewModel(client: MockClient())
        await home.load()
        let widgets = home.state.widgets
        #expect(widgets.isSampleData)
        let overview = try #require(widgets.overview.value)
        #expect(overview.balance == 8040.22)
        #expect(overview.netWorthChart.points.count == 3)
        #expect(overview.accounts.map(\.kindLabel) == ["Current account", "Savings", "Credit card"])
        let spending = try #require(widgets.spending.value)
        #expect(spending.monthText == "October 2026")
        #expect(spending.categories.first?.changeText == "Same as last month")
        #expect(spending.categories[1].changeText == "Up 6% on last month")
        let subscriptions = try #require(widgets.subscriptions.value)
        #expect(subscriptions.countText == "2 subscriptions")
        #expect(subscriptions.priceRiseCount == 1)
        #expect(subscriptions.items[0].priceRiseText == "Price went up from £10.99 to £12.99 on 28 Jun 2026")
        #expect(widgets.subscriptions.moveLink?.moveID == "mv_cancel_subs")
        #expect(widgets.bills.moveLink?.moveID == "mv_fix_mortgage")
        #expect(widgets.budgets.moveLink == nil, "No cut_budget move in the example")
        let budgets = try #require(widgets.budgets.value)
        #expect(budgets.items[0].statusText == "£22 over")
        #expect(budgets.items[0].status == .over)
        let goal = try #require(widgets.goals.value?.first)
        #expect(goal.planText == "Save £429 a month to reach it by 1 Jun 2029")
    }

    @Test func widgetLinkFocusesNextMove() async {
        let home = MoneyHomeViewModel(client: MockClient())
        await home.load()
        home.actions.widgets.onShowMove("mv_cancel_subs")
        #expect(home.state.nextMove.displayedMove?.id == "mv_cancel_subs")
    }

    @Test func failedWidgetDoesNotBlockOthers() {
        let state = MoneyWidgetsViewModel.makeState(
            overview: .failure(.network), spending: .success(ContractExamples.spending),
            subscriptions: nil, bills: nil, budgets: nil, goals: nil, moves: []
        )
        #expect(state.overview.phase == .failed(.from(.network)))
        #expect(state.spending.phase == .ready)
        #expect(state.subscriptions.phase.isLoading)
    }

    @Test func budgetUpdateChangesStatus() async throws {
        let client = MockClient()
        let updated = try await client.updateBudgets([.init(category: .eatingOut, limit: 180)])
        let eatingOut = try #require(updated.items.first { $0.category == .eatingOut })
        #expect(eatingOut.limit == 180)
        #expect(eatingOut.status == .near)
    }

    // MARK: Guess my spend (ADR 0017)

    @Test func guessHidesPredictionUntilGuessed() async throws {
        let model = GuessSpendViewModel(client: MockClient())
        await model.load()
        #expect(model.state.stage == .guessing)
        #expect(model.state.reveal == nil, "No prediction before the guess")
        #expect(model.state.isToday)
        #expect(model.state.dateText == "Today, Sat 17 Oct")
        #expect(model.state.weatherText == "Light rain, 13.5°C")
        await model.submit("£30")
        #expect(model.state.stage == .revealed)
        let reveal = try #require(model.state.reveal)
        #expect(reveal.guess == 30)
        #expect(reveal.predictedText == "£38.40")
        #expect(reveal.rangeText == "Likely between £12.00 and £71.50")
        #expect(reveal.reasons.map(\.effectText) == ["+£9.80", "+£6.20", "-£1.70"])
        #expect(reveal.comparisonText == "Your guess is £8.40 under the model.")
        #expect(reveal.resultText == nil, "Actual not known yet")
    }

    @Test func secondGuessShowsServerError() async {
        let model = GuessSpendViewModel(client: MockClient())
        await model.load()
        await model.submit("30")
        await model.submit("31")
        #expect(model.state.errorMessage == "You already guessed for this day.")
        #expect(model.state.reveal?.guess == 30)
    }

    @Test func invalidGuessIsRejectedLocally() async {
        let model = GuessSpendViewModel(client: MockClient())
        await model.load()
        await model.submit("lots")
        #expect(model.state.errorMessage == "Enter an amount in pounds, for example 25.")
        #expect(model.state.stage == .guessing)
        #expect(GuessSpendViewModel.parseGuess("1,200.505") == 1200.51)
        #expect(GuessSpendViewModel.parseGuess("-1") == nil)
        #expect(GuessSpendViewModel.parseGuess("100001") == nil)
    }

    @Test func pastDayShowsActualPointsAndBeatModel() async throws {
        let model = GuessSpendViewModel(client: MockClient())
        await model.load()
        await model.load(date: "2026-10-16")
        let state = model.state
        #expect(!state.isToday)
        #expect(state.stage == .revealed)
        let reveal = try #require(state.reveal)
        #expect(reveal.actualText == "You spent £24.10.")
        #expect(reveal.resultText == "You beat the model. 96 points.")
        #expect(reveal.rangeText == "Likely between £9.00 and £55.20")
        #expect(state.streakText == "3 days in a row with 70 points or more. Best: 5.")
        #expect(state.pointsTotal == 412)
        #expect(state.history.first?.summary == "You guessed £25.00, spent £24.10. 96 points. You beat the model.")
    }

    @Test func spendAccuracyMapsBacktest() async {
        let model = SpendAccuracyViewModel(client: MockClient())
        await model.load()
        #expect(model.state.modelText == "The model is off by £11.30 on a typical day.")
        #expect(model.state.baselineText == "Average spend for that weekday is off by £14.90.")
        #expect(model.state.coverageText == "81% of days fell inside the range.")
        #expect(model.state.days.first?.isInRange == true)
    }

    // MARK: Play, You, Evaluation, Life menu

    @Test func playListsLivesChallengesAndStartsChallenge() async {
        let session = GameSession(client: MockClient())
        let model = PlayViewModel(session: session)
        await model.load()
        #expect(model.state.lives.map(\.name) == ["Amira"])
        #expect(model.state.lives[0].detail == "Age 26 in 2008")
        #expect(model.state.challenges.first?.detail == "Starts in 2006")
        #expect(model.state.conceptsText == "0 of \(ContractExamples.concepts.count) concepts collected")
        var route: PlayViewModel.Route?
        model.onRoute = { route = $0 }
        await model.startChallenge("home-by-30")
        #expect(route == .life)
        #expect(session.life?.startYear == 2006)
        #expect(session.phase == .playing)
        await model.load()
        #expect(model.state.lives.first?.isCurrent == true)
        #expect(model.state.continueText?.hasPrefix("Continue as Amira") == true)
    }

    @Test func openLifeLoadsStoredLife() async {
        let session = GameSession(client: MockClient())
        _ = await session.startLife(CharacterChoice(mode: .preset, character: ContractExamples.characters.presets[0]).request(startYear: 2006))
        let id = session.life!.id
        session.newLife()
        #expect(await session.openLife(id: id))
        #expect(session.phase == .playing)
        #expect(!(await session.openLife(id: "lf_missing")))
        #expect(session.errorMessage != nil)
    }

    @Test func youShowsProfileFromFinanceData() async throws {
        let model = YouViewModel(client: MockClient())
        await model.load()
        let profile = try #require(model.state.profile)
        #expect(profile.detail == "Analyst in Leeds, age 34")
        #expect(profile.housingText == "Renting, £850 a month")
        #expect(model.state.personalFacts == ["You spend £47 a month on 6 subscriptions."])
        #expect(model.state.bankText == "Not connected. The Money tab shows sample data.")
        var route: YouViewModel.Route?
        model.onRoute = { route = $0 }
        model.actions.onConnectBank()
        #expect(route == .bank)
    }

    @Test func evaluationMapsBacktest() async {
        let model = EvaluationViewModel(client: MockClient())
        await model.load()
        #expect(model.state.hitText == "Right in 67% of 24 past periods.")
        #expect(model.state.baselineText == "Always fix 2 years: right in 50%.")
        #expect(model.state.periods.first?.detail == "Advice: Fix 5y. Best in hindsight: Fix 5y.")
    }

    @Test func lifeMenuCountsEnabledActions() {
        let state = LifeMenuViewModel.makeState(life: Fixtures.midLife)
        #expect(state.items.map(\.title) == ["Job", "Assets", "People", "Money", "Activities"])
        #expect(state.isEnabled)
        #expect(state.items.first { $0.menu == .assets }!.count >= 1)
        #expect(!LifeMenuViewModel.makeState(life: nil).isEnabled)
    }

    // MARK: Tabs and gallery

    @Test func appOpensOnMoneyTab() {
        #expect(AppTab.launch == .money)
        #expect(AppTab.allCases.map(\.title) == ["Money", "Life", "Play", "Friends", "You"])
    }

    @Test func galleryCatalogHasUniqueIDsAndNewScreens() {
        let ids = Fixtures.galleryCatalog.sections.flatMap(\.entries).map(\.id)
        #expect(Set(ids).count == ids.count)
        #expect(ids.contains("nextMove.ready"))
        #expect(ids.contains("guess.before"))
        #expect(ids.contains("testit.ready"))
        #expect(GalleryViewModel.catalog == Fixtures.galleryCatalog)
    }
}
