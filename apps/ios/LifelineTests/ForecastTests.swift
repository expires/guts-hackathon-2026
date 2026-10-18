import Foundation
import Testing
@testable import Lifeline

/// ADR 0072 (PENNY_V3_BUILD.md B3): forecast card, The maths, Detailed breakdown, All spending, Category.
@MainActor
@Suite("Forecast Next Move (ADR 0072)")
struct ForecastTests {
    // MARK: Forecast card

    @Test func onTrackCardMatchesTheCanvas() {
        let card = ForecastFixtures.card(.onTrack)
        #expect(card.status == .onTrack)
        #expect(card.chipText == "On track")
        #expect(card.headline == "You'll make it to 2 November")
        #expect(card.subline == "Your next money: SAAS loan, £735.")
        #expect(card.budgetLead == "You can spend")
        #expect(card.weeklyAmount == "£135")
        #expect(card.dailyText == "(about £19 a day)")
        #expect(card.habitLine == "You usually spend £122, so you'll have about £26 spare.")
        #expect(card.timeline.map(\.title) == ["Today", "Phone £12", "Spotify £6", "Loan £735"])
        #expect(card.timeline.map(\.dateText) == ["18 Oct", "24 Oct", "28 Oct", "2 Nov"])
    }

    @Test func runningShortCardMatchesTheCanvas() {
        let card = ForecastFixtures.card(.short)
        #expect(card.status == .runningShort)
        #expect(card.chipText == "Running short")
        #expect(card.headline == "At this pace, you run out on 28 October")
        #expect(card.subline == "That's 5 days before your next money on 2 November.")
        #expect(card.budgetLead == "Keep it under")
        #expect(card.weeklyAmount == "£80")
        #expect(card.dailyText == "(about £11 a day)")
        #expect(card.habitLine == "You usually spend £118. Eating out is your biggest cost: £52 a week.")
        #expect(card.timeline.map(\.kind) == [.today, .bill, .runOut, .nextMoney])
        #expect(card.timeline.map(\.title) == ["Today", "Bills £30", "Runs out", "Pay £410"])
        let help = ForecastHelpState.make(ForecastFixtures.forecast(.short))
        #expect(help?.kind == .cut)
    }

    @Test func noNextMoneyCardHasNoWeeklyFigure() {
        let card = ForecastCardState.make(ForecastFixtures.noNextMoney)
        #expect(card.status == .noNextMoney)
        #expect(card.chipText == "No money due yet")
        #expect(card.weeklyAmount == nil)
        #expect(card.budgetLead == nil)
        #expect(card.dailyText == nil)
        #expect(card.timeline.isEmpty)
        #expect(ForecastDueState.make(ForecastFixtures.noNextMoney) == nil)
        #expect(ForecastMathsState.make(ForecastFixtures.noNextMoney).sum == nil)
    }

    @Test func dueBeforeAndHelpUseTheForecast() {
        let forecast = ForecastFixtures.forecast(.onTrack)
        let due = ForecastDueState.make(forecast)
        #expect(due?.title == "Due before 2 November")
        #expect(due?.totalText == "£18")
        #expect(due?.rows.map(\.name) == ["Phone · EE", "Spotify Student"])
        let help = ForecastHelpState.make(forecast)
        #expect(help?.title == "Put your £26 spare aside on 2 November")
        #expect(help?.detail == "Easy-access savings pay about 3.5% a year. Source: Bank of England.")
    }

    @Test func manyBillsMergeIntoOneTimelinePoint() {
        var persona = ForecastMock.onTrack
        persona.bills += [
            .init(name: "Gym", short: "Gym", kind: "subscription", pence: 1_500, due: "2026-10-26"),
            .init(name: "Netflix", short: "Netflix", kind: "subscription", pence: 499, due: "2026-10-30"),
        ]
        let card = ForecastCardState.make(ForecastMock.forecast(persona))
        #expect(card.timeline.count <= 5)
        #expect(card.timeline.first?.kind == .today)
        #expect(card.timeline.last?.kind == .nextMoney)
        #expect(card.timeline.contains { $0.title.hasPrefix("Bills ") })
    }

    // MARK: The maths

    @Test func mathsShowsFourStepsWithSourcesAndTheSum() {
        let state = ForecastMathsState.make(ForecastFixtures.forecast(.onTrack))
        #expect(state.intro == "How Penny got £135 a week.")
        #expect(state.steps.map(\.amountText) == ["£318", "\u{2212}£18", "\u{2212}£30", "2 Nov · £735"])
        #expect(state.steps[0].detail == "Your account today · Your statement")
        #expect(state.steps[3].detail.contains("SAAS"))
        #expect(state.sum?.line == "£270 left ÷ 2 weeks")
        #expect(state.sum?.result == "= £135 a week")
        #expect(state.sum?.daily == "About £19 a day")
        #expect(state.habits?.text == "You spent £122 a week on average over the last 4 weeks. That's £13 under £135, so you're on track.")
        #expect(state.habits?.source == "Your statement, 20 Sep to 17 Oct")
        #expect(state.bufferPct == 10)
    }

    @Test func bufferChangePreviewsThenSaves() async throws {
        let client = MockClient()
        let model = ForecastMathsViewModel(client: client)
        await model.load()
        #expect(model.state.bufferPct == 10)
        var changed: Forecast?
        model.onForecastChanged = { changed = $0 }
        await model.selectBuffer(20)
        let state = model.state
        #expect(state.bufferPct == 20)
        #expect(state.bufferError == nil)
        #expect(!state.isUpdatingBuffer)
        #expect(state.steps[2].amountText == "\u{2212}£60")
        #expect(changed?.bufferPct == ._20)
        // Saved: the stored setting is now 20.
        let stored = try await client.forecast(bufferPct: nil, stress: nil)
        #expect(stored.bufferPct == ._20)
        #expect(stored.perWeek < ForecastFixtures.forecast(.onTrack).perWeek)
    }

    @Test func stressTestShowsTheResultInline() async {
        let model = ForecastMathsViewModel(client: MockClient(), forecast: ForecastFixtures.forecast(.onTrack))
        await model.runStress()
        guard case let .result(text, source, stillOK) = model.state.stress else {
            Issue.record("Expected a stress result, got \(model.state.stress)")
            return
        }
        #expect(text.contains("2022"))
        #expect(source.contains("ONS"))
        #expect(stillOK)
    }

    /// Fewer than 14 days to the next money: the total until the date, and a day compared with a day.
    @Test func fewerThanTwoWeeksShowsTheTotalUntilTheDate() throws {
        let forecast = ForecastFixtures.forecast(.soon)
        #expect(forecast.budgetPeriod == .untilNextMoney)
        #expect(forecast.days == 9)
        let toSpend = try #require(forecast.toSpend)
        let card = ForecastCardState.make(forecast)
        #expect(card.weeklyAmount == "£276")
        #expect(card.weeklyAmount == ForecastText.whole(toSpend))
        #expect(card.unitText == "until 28 Oct")
        #expect(card.dailyText == "(about £31 a day)")
        let maths = ForecastMathsState.make(forecast)
        #expect(maths.intro == "How Penny got £276 until 28 Oct.")
        #expect(maths.sum?.line == "£276 left ÷ 9 days")
        #expect(maths.sum?.result == "= £31 a day")
        #expect(maths.sum?.daily == nil)
        #expect(maths.habits?.text.hasPrefix("You spent £17 a day on average over the last 4 weeks.") == true)
        let breakdown = ForecastBreakdownState.make(forecast)
        #expect(breakdown.sections[4].rows.map(\.label) == ["Money to spend", "Per day"])
        #expect(breakdown.sections[4].rows[0].value == ForecastText.pence(toSpend))
        #expect(breakdown.sections[4].source == "Rounded to £276 until 28 Oct and £31 a day on the card")
    }

    /// Overdrawn: nothing to spend, so the card shows the server's line, never "Keep it under £0".
    @Test func overdrawnShowsTheServersLine() {
        let forecast = ForecastFixtures.forecast(.overdrawn)
        #expect(forecast.state == .runningShort)
        #expect(forecast.perDay == 0)
        let card = ForecastCardState.make(forecast)
        #expect(card.budgetNote == forecast.budgetLine)
        #expect(card.budgetNote == "You are £50 short before 2 November")
        #expect(card.weeklyAmount == nil)
        #expect(card.budgetLead == nil)
        #expect(!card.accessibilitySummary.contains("£0"))
        let maths = ForecastMathsState.make(forecast)
        #expect(maths.sum?.result == forecast.budgetLine)
    }

    @Test func whatIfOpensPennyWithTheForecastAndNoQuestion() {
        let route = PennyRoute.whatIf
        #expect(route.screen == .forecast)
        #expect(route.question == nil)
        #expect(route.title == "What if...")
    }

    // MARK: Detailed breakdown

    @Test(arguments: [0, 5, 10, 15, 20])
    func breakdownAddsUpToThePenny(bufferPct: Int) {
        for student in [ForecastFixtures.Student.onTrack, .short, .soon] {
            let forecast = ForecastFixtures.forecast(student, bufferPct: bufferPct)
            #expect(ForecastText.toPence(forecast.toSpend ?? 0) == ForecastBreakdownState.make(forecast).sums.toSpend)
            let sums = ForecastBreakdownState.make(forecast).sums
            #expect(sums.moneyAddsUp)
            #expect(sums.billsAddUp)
            #expect(sums.moneyNow - sums.billsTotal - sums.buffer == sums.toSpend)
            #expect(sums.usualWeeks.count == forecast.usualWeeks.count)
            let average = Double(sums.usualWeeks.reduce(0, +)) / Double(sums.usualWeeks.count)
            #expect(abs(average - Double(sums.usualWeekly)) <= 1)
            // The engine's per week is the money to spend over the days, times 7.
            let perWeek = Double(sums.toSpend) * 7 / Double(forecast.days)
            #expect(abs(perWeek - forecast.perWeek * 100) <= 1)
        }
    }

    @Test func breakdownShowsPenceAndEveryBlock() {
        let state = ForecastBreakdownState.make(ForecastFixtures.forecast(.onTrack))
        #expect(state.sections.map(\.number) == [1, 2, 3, 4, 5, 6, 7])
        #expect(state.sections.allSatisfy { !$0.source.isEmpty })
        let money = state.sections[0].rows
        #expect(money.map(\.value) == ["£318.40", "£300.00", "£318.40"])
        #expect(money[1].note != nil, "Savings are listed but not counted")
        #expect(state.sections[1].rows.last?.value == "\u{2212}£17.99")
        #expect(state.sections[2].rows.last?.value == "\u{2212}£30.04")
        let sum = state.sections[4].rows
        #expect(sum[0].value == "£270.37")
        #expect(sum[0].note == "£318.40 \u{2212} £17.99 \u{2212} £30.04")
        #expect(state.sections[3].rows[1].value == "14")
        #expect(state.closing?.contains("still make it to 2 November") == true)
    }

    @Test func runningShortBreakdownShowsTheRunOutDay() {
        let state = ForecastBreakdownState.make(ForecastFixtures.forecast(.short))
        let last = state.sections.last
        #expect(last?.title == "When the money runs out")
        #expect(last?.rows.last?.value == "28 October")
    }

    /// Expected income (weekly pay before the main next money) adds to money available, and the sum still adds up.
    @Test func expectedIncomeIsAddedAndStillAddsUp() {
        var persona = ForecastMock.short
        persona.expected = [.init(label: "Pay from the bar job", pence: 4_000, date: "2026-10-25", source: "Your statement")]
        let forecast = ForecastMock.forecast(persona)
        #expect(forecast.incomeExpectedTotal == 40)
        let maths = ForecastMathsState.make(forecast)
        #expect(maths.steps[0].amountText == ForecastText.whole(forecast.moneyNow + 40))
        #expect(maths.steps[0].detail.hasPrefix("Money now £208 + expected before 2 Nov £40"))
        let breakdown = ForecastBreakdownState.make(forecast)
        let sums = breakdown.sums
        #expect(sums.moneyAddsUp)
        #expect(sums.expectedTotal == 4_000)
        #expect(sums.moneyNow + sums.expectedTotal - sums.billsTotal - sums.buffer == sums.toSpend)
        #expect(abs(Double(sums.toSpend) * 7 / Double(forecast.days) - forecast.perWeek * 100) <= 1)
        #expect(breakdown.sections[0].rows.contains { $0.label == "Pay from the bar job" && $0.value == "£40.00" })
        #expect(breakdown.sections[0].rows.last?.value == ForecastText.pence(forecast.moneyNow + 40))
    }

    // MARK: All spending

    @Test func allSpendingSwitchesThroughEveryStatementMonth() async throws {
        let client = MockClient()
        let model = AllSpendingViewModel(client: client)
        await model.load()
        let months = model.months
        #expect(months.count == 4)
        #expect(model.state.canGoBack)
        #expect(!model.state.canGoForward)
        let current = try #require(model.state.pie)
        #expect(current.isCurrent)
        await model.show(months[0])
        #expect(model.state.pie?.month == months[0])
        #expect(!model.state.canGoBack)
        #expect(model.state.canGoForward)
        #expect(model.state.pie?.isCurrent == false)
        #expect(model.state.pie?.rangeText == "Whole month")
        await model.show(months[1])
        // Change against the month before, in pounds.
        let changes = model.state.pie?.slices.compactMap(\.changeText) ?? []
        #expect(!changes.isEmpty)
        #expect(changes.allSatisfy { $0.hasSuffix(ForecastText.shortMonth(months[0])) })
    }

    @Test func allSpendingListsRentAndBillsApart() throws {
        let state = ForecastFixtures.allSpending
        let pie = try #require(state.pie)
        #expect(pie.totalText == "£268")
        #expect(pie.slices.map(\.label) == ["Groceries", "Eating out", "Going out", "Transport", "Shopping"])
        #expect(pie.slices.map(\.shareText) == ["36%", "24%", "16%", "14%", "10%"])
        #expect(Set(pie.fixed.map(\.id)) == ["housing", "bills"])
        #expect(!pie.slices.contains { $0.id == "housing" })
        #expect(pie.periodText == "October so far")
        #expect(pie.rangeText == "1 to 18 Oct · so far")
    }

    // MARK: Category

    @Test func categoryScreenShowsTotalWeeksAndEveryPayment() async throws {
        let client = MockClient()
        let model = CategoryDetailViewModel(client: client, category: "groceries", label: "Groceries", month: nil)
        await model.load()
        let detail = try #require(model.detail)
        let state = model.state
        #expect(state.phase == .ready)
        #expect(state.title == detail.label)
        #expect(state.totalText == Money.format(detail.total))
        #expect(state.payments.count == detail.transactions.count)
        #expect(state.askTitle == "Ask Penny about groceries")
        #expect(state.usualText?.hasPrefix("You usually spend about") == true)
        // Weeks and payments add up to the total, to the penny.
        let total = ForecastText.toPence(detail.total)
        #expect(detail.weeks.reduce(0) { $0 + ForecastText.toPence($1.amount) } == total)
        #expect(detail.transactions.reduce(0) { $0 + ForecastText.toPence(abs($1.amount)) } == total)
        #expect(state.bars.count == detail.weeks.count)
        #expect(state.bars.map(\.fraction).max() == 1)
    }

    @Test func askPennyRoutesCarryTheForecastContext() {
        let route = PennyRoute.weeklyBudget
        #expect(route.screen == .forecast)
        #expect(route.question == "Explain my weekly budget")
        #expect(PennyRoute.category("Groceries").question == "Explain my spending on groceries")
    }

    // MARK: No "Mock data" or "Sample data" on Money screens (B4)

    @Test func moneyScreensShowNoMockOrSampleDataText() async {
        let client = MockClient()
        let home = MoneyHomeViewModel(client: client)
        await home.load()
        let maths = ForecastMathsViewModel(client: client)
        await maths.load()
        let spending = AllSpendingViewModel(client: client)
        await spending.load()
        let category = CategoryDetailViewModel(client: client, category: "groceries", label: "Groceries", month: nil)
        await category.load()
        let texts = Self.strings(home.state) + Self.strings(maths.state) + Self.strings(spending.state) + Self.strings(category.state)
            + Self.strings(ForecastBreakdownState.make(ForecastFixtures.forecast(.onTrack)))
        #expect(!texts.isEmpty)
        for text in texts {
            #expect(!text.localizedCaseInsensitiveContains("mock data"), "\(text)")
            #expect(!text.localizedCaseInsensitiveContains("sample data"), "\(text)")
            #expect(!text.contains("\u{2014}"), "No em dashes: \(text)")
        }
        #expect(!home.state.isSampleData)
    }

    /// Every string shown by a Money screen state, except the old parts Money home no longer draws.
    private static func strings(_ value: Any) -> [String] {
        var found: [String] = []
        func walk(_ value: Any, depth: Int) {
            guard depth < 12 else { return }
            if let text = value as? String { found.append(text); return }
            for child in Mirror(reflecting: value).children {
                if let label = child.label, ["nextMove", "widgets", "guess", "badgeText", "comingUp"].contains(label) { continue }
                walk(child.value, depth: depth + 1)
            }
        }
        walk(value, depth: 0)
        return found
    }
}
