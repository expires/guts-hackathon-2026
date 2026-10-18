import Foundation
import Testing
@testable import Lifeline

/// ADR 0072: Money home block order, £0 categories hidden, "Hi, <name>" greeting, Test it card logic (old screens kept).
@MainActor
@Suite("Money home redesign (ADR 0070)")
struct MoneyHomeRedesignTests {
    // MARK: Block order (ADR 0072)

    @Test func blocksFollowTheForecastOrder() {
        let state = ForecastFixtures.home(.onTrack)
        #expect(state.blocks == [.forecast, .spending, .due, .help, .accountLine])
    }

    @Test func optionalBlocksDropOutWithoutChangingTheOrder() {
        var state = ForecastFixtures.home(.onTrack)
        state.help = nil
        state.due = nil
        state.moneyNow = nil
        #expect(state.blocks == [.forecast, .spending])
        #expect(state.accountLineText == nil)
    }

    @Test func noBlocksBeforeTheMoneyLoads() {
        #expect(Fixtures.MoneyHome.loading.blocks.isEmpty)
        #expect(Fixtures.MoneyHome.noData.blocks.isEmpty)
        #expect(Fixtures.MoneyHome.offline.blocks.isEmpty)
    }

    @Test func accountLineUsesTheForecastMoneyNow() async throws {
        let client = MockClient()
        let home = MoneyHomeViewModel(client: client)
        await home.load()
        let forecast = try await client.forecast(bufferPct: nil, stress: nil)
        let state = home.state
        #expect(state.accountLineText == "In your account \(Money.format(forecast.moneyNow))")
        #expect(state.blocks.first == .forecast)
        #expect(state.blocks.last == .accountLine)
    }

    @Test func homeLoadsTheForecastAndSpending() async {
        let home = MoneyHomeViewModel(client: MockClient())
        await home.load()
        let state = home.state
        #expect(state.forecastPhase == .ready)
        #expect(state.forecast?.status == .onTrack)
        #expect(state.spendingPhase == .ready)
        #expect((state.spending?.top.count ?? 0) <= 5)
        #expect(state.due?.rows.isEmpty == false)
        #expect(state.help?.kind == .save)
    }

    /// B4: the old Next Move card, weekly budget block, balance tiles and Guess my spend are gone from Money home.
    @Test func oldMoneyHomeBlocksAreGone() async {
        let home = MoneyHomeViewModel(client: MockClient())
        await home.load()
        let names = home.state.blocks.map(\.rawValue)
        for removed in ["nextMove", "weeklyBudget", "bills", "subscriptions", "budgetsAndGoals", "guess"] {
            #expect(!names.contains(removed))
        }
        #expect(home.state.tiles == nil)
        #expect(home.state.weeklyBudget == nil)
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
        let pie = SpendingPieState.make(ForecastFixtures.spending)
        let amounts = pie.top.map(\.amount)
        #expect(amounts == amounts.sorted(by: >))
        #expect(amounts.allSatisfy { $0.rounded() > 0 })
        #expect(pie.top.count == 5)
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

    /// G1: "Hi, <first name>" at every time of day.
    @Test(arguments: [0, 4, 5, 8, 12, 14, 18, 20, 23])
    func greetingIsHiAtEveryHour(hour: Int) {
        let header = MoneyHomeViewModel.header(profile: nil, now: Self.date(hour: hour), calendar: Self.london)
        #expect(header.greeting == "Hi")
        #expect(MoneyHomeViewModel.greeting(name: "Eilidh") == "Hi, Eilidh")
    }

    @Test func greetingUsesTheInjectedClockButStaysHi() {
        let model = MoneyHomeViewModel(client: MockClient(), now: { Self.date(hour: 8, minute: 30) }, calendar: Self.london)
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
}
