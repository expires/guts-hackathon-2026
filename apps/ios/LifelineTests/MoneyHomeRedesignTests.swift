import Foundation
import Testing
@testable import Lifeline

/// ADR 0070: Money home block order, £0 categories hidden, local-time greeting, Test it always shown when testable.
@MainActor
@Suite("Money home redesign (ADR 0070)")
struct MoneyHomeRedesignTests {
    // MARK: Block order

    @Test func blocksFollowTheADROrder() {
        var state = Fixtures.MoneyHome.ready
        state.weeklyBudget = .init(moveID: "mv_week", text: "Until 2 November: spend up to £82 a week", detail: nil)
        #expect(state.blocks == [
            .nextMove, .weeklyBudget, .spending, .bills, .subscriptions, .budgetsAndGoals, .accountLine, .guess,
        ])
    }

    @Test func optionalBlocksDropOutWithoutChangingTheOrder() {
        var state = Fixtures.MoneyHome.ready
        state.weeklyBudget = nil
        state.tiles = nil
        #expect(state.blocks == [.nextMove, .spending, .bills, .subscriptions, .budgetsAndGoals, .guess])
        #expect(state.accountLineText == nil)
    }

    @Test func noBlocksBeforeTheMoneyLoads() {
        #expect(Fixtures.MoneyHome.loading.blocks.isEmpty)
        #expect(Fixtures.MoneyHome.noData.blocks.isEmpty)
        #expect(Fixtures.MoneyHome.offline.blocks.isEmpty)
    }

    @Test func accountLineUsesTheHomeNumbers() async throws {
        let client = MockClient()
        let home = MoneyHomeViewModel(client: client)
        await home.load()
        let expected = try await client.financeHome()
        let balance = try #require(expected.balance)
        let netWorth = try #require(expected.netWorth)
        let state = home.state
        #expect(state.accountLineText == "In your account \(Money.format(balance)) · Net worth \(Money.format(netWorth))")
        #expect(state.blocks.first == .nextMove)
        #expect(state.blocks.last == .guess)
        #expect(state.blocks.firstIndex(of: .accountLine)! > state.blocks.firstIndex(of: .budgetsAndGoals)!)
    }

    @Test func homeLoadsTheWidgetBlocks() async {
        let home = MoneyHomeViewModel(client: MockClient())
        await home.load()
        let widgets = home.state.widgets
        #expect(widgets.spending.phase == .ready)
        #expect(widgets.bills.phase == .ready)
        #expect(widgets.subscriptions.phase == .ready)
        #expect(widgets.budgets.phase == .ready)
        #expect(widgets.goals.phase == .ready)
        #expect(home.state.billsShown.count <= 3)
        #expect(home.state.topCategories.count <= 4)
    }

    // MARK: Home without next_move (slow server)

    @Test func homeWithoutNextMoveKeepsSkeletonThenFetchesTheMove() async throws {
        let client = MockClient()
        var slowHome = try await client.financeHome()
        try #require(slowHome.hasData)
        slowHome.nextMove = nil
        let home = MoneyHomeViewModel(client: client)
        home.apply(slowHome)
        // Never "No move right now" while the move is only late.
        #expect(home.state.nextMove.phase.isLoading)
        #expect(home.state.nextMove.top == nil)
        await home.loadMoveIfNeeded()
        let expected = try await client.nextMove()
        #expect(home.state.nextMove.phase == .ready)
        #expect(home.state.nextMove.top?.id == expected.top.id)
        #expect(home.widgets.moves.first?.id == expected.top.id)
        // A later home without next_move keeps the move on screen.
        home.apply(slowHome)
        #expect(home.state.nextMove.top?.id == expected.top.id)
    }

    @Test func homeWithNextMoveInEnglishNeedsNoSecondCall() async throws {
        let client = MockClient()
        let home = MoneyHomeViewModel(client: client)
        await home.load()
        let expected = try await client.financeHome()
        #expect(home.state.nextMove.top?.id == expected.nextMove?.top.id)
        #expect(home.state.nextMove.phase == .ready)
    }

    // MARK: £0 categories

    @Test func zeroPoundCategoriesAreHidden() throws {
        var response = ContractExamples.spending
        try #require(response.categories.count >= 3)
        response.categories[0].amount = 0
        response.categories[1].amount = 0.4
        let kept = response.categories[2]
        let state = MoneyWidgetsViewModel.spending(response)
        #expect(!state.categories.contains { $0.id == response.categories[0].category.rawValue })
        #expect(!state.categories.contains { $0.id == response.categories[1].category.rawValue })
        #expect(state.categories.contains { $0.id == kept.category.rawValue })
        #expect(state.categories.allSatisfy { $0.amount.rounded() > 0 })
        // The total stays the API's own number.
        #expect(state.total == response.total)
    }

    @Test func topCategoriesAreLargestFirstAndNeverZero() {
        let state = Fixtures.MoneyHome.ready
        let amounts = state.topCategories.map(\.amount)
        #expect(amounts == amounts.sorted(by: >))
        #expect(amounts.allSatisfy { $0.rounded() > 0 })
    }

    // MARK: Greeting by local time

    private nonisolated static let london: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Europe/London")!
        return calendar
    }()

    /// 18 Oct 2026 at `hour`:`minute` in London.
    private nonisolated static func date(hour: Int, minute: Int = 0) -> Date {
        london.date(from: DateComponents(year: 2026, month: 10, day: 18, hour: hour, minute: minute))!
    }

    @Test(arguments: [
        (4, 59, MoneyHomeViewModel.DayPart.lateNight),
        (5, 0, .morning),
        (11, 59, .morning),
        (12, 0, .afternoon),
        (17, 59, .afternoon),
        (18, 0, .evening),
        (22, 59, .evening),
        (23, 0, .lateNight),
        (0, 0, .lateNight),
    ])
    func greetingBoundaries(hour: Int, minute: Int, part: MoneyHomeViewModel.DayPart) {
        let header = MoneyHomeViewModel.header(profile: nil, now: Self.date(hour: hour, minute: minute), calendar: Self.london)
        #expect(header.greeting == MoneyHomeViewModel.greeting(part, name: nil))
    }

    @Test func greetingWordsInEnglish() {
        #expect(MoneyHomeViewModel.header(profile: nil, now: Self.date(hour: 8), calendar: Self.london).greeting == "Morning")
        #expect(MoneyHomeViewModel.header(profile: nil, now: Self.date(hour: 14), calendar: Self.london).greeting == "Afternoon")
        #expect(MoneyHomeViewModel.header(profile: nil, now: Self.date(hour: 20), calendar: Self.london).greeting == "Evening")
        #expect(MoneyHomeViewModel.header(profile: nil, now: Self.date(hour: 2), calendar: Self.london).greeting == "Hi")
        #expect(MoneyHomeViewModel.greeting(.lateNight, name: "Priya") == "Hi, Priya")
        #expect(MoneyHomeViewModel.greeting(.morning, name: "Priya") == "Morning, Priya")
    }

    @Test func greetingUsesTheInjectedClock() {
        let model = MoneyHomeViewModel(client: MockClient(), now: { Self.date(hour: 23, minute: 30) }, calendar: Self.london)
        #expect(model.state.header.greeting == "Hi")
    }

    @Test func greetingIsTranslated() {
        #expect(L10n.tr("Morning", language: .fr) == "Bonjour")
        #expect(L10n.tr("Hi", language: .zhHans) == "你好")
        #expect(L10n.tr("Evening", language: .hi) == "शुभ संध्या")
        let name = "Priya"
        #expect(L10n.tr("Afternoon, \(name)", language: .es) == "Buenas tardes, Priya")
        for language in AppLanguage.allCases where language != .en {
            for key: String.LocalizationValue in ["Morning", "Afternoon", "Evening", "Hi"] {
                #expect(L10n.tr(key, language: language) != L10n.tr(key, language: .en), "\(language) misses a greeting")
            }
        }
    }

    // MARK: Test it

    private static func move(testable: Bool, id: String = "mv_a") -> Move {
        ContractExamples.decode("""
        {"id": "\(id)", "kind": "cancel_subscription", "action": "Cancel 2 subscriptions", "headline": "Unused for 3 months",
         "impact_per_year": 264, "worst_case_per_year": 200, "confidence": 0.8, "confidence_label": "x",
         "evidence": [], "sources": [], "options": [], "testable": \(testable)}
        """)
    }

    @Test func testItShowsWheneverTheMoveIsTestable() {
        for inPlan in [false, true] {
            #expect(NextMoveCardView.showsTestIt(NextMoveViewModel.move(Self.move(testable: true), isInPlan: inPlan)))
            #expect(!NextMoveCardView.showsTestIt(NextMoveViewModel.move(Self.move(testable: false), isInPlan: inPlan)))
        }
    }

    @Test func testItShowsForAFocusedTestableRunnerUp() async throws {
        let model = NextMoveViewModel(client: MockClient())
        await model.load()
        let runnerUp = try #require(model.state.runnersUp.first)
        model.focus(runnerUp.id)
        let shown = try #require(model.state.displayedMove)
        #expect(shown.id == runnerUp.id)
        #expect(NextMoveCardView.showsTestIt(shown) == model.move(runnerUp.id)?.testable)
        var opened: String?
        model.onTestIt = { opened = $0 }
        model.actions.onTestIt(shown.id)
        #expect((opened != nil) == (model.move(runnerUp.id)?.testable == true))
    }

    @Test func topTestableMoveShowsTestItOnMoneyHome() async throws {
        let home = MoneyHomeViewModel(client: MockClient())
        await home.load()
        let top = try #require(home.state.nextMove.displayedMove)
        let move = try #require(home.nextMove.move(top.id))
        #expect(NextMoveCardView.showsTestIt(top) == move.testable)
    }
}
