import Foundation
import Testing
@testable import Lifeline

/// Presentation mode (milestone 4) in W7 screens: amounts rounded, pence hidden, names generic.
@MainActor
@Suite("Presentation mode (W7 screens)")
struct PresentationModeTests {
    /// Every pound amount in `text` is a multiple of £10 and has no pence.
    static func onlyRoundedAmounts(_ text: String) -> Bool {
        guard let regex = try? NSRegularExpression(pattern: #"£([\d,]+)(\.\d+)?"#) else { return false }
        let matches = regex.matches(in: text, range: NSRange(text.startIndex..., in: text))
        return matches.allSatisfy { match in
            guard match.range(at: 2).location == NSNotFound,
                  let range = Range(match.range(at: 1), in: text),
                  let value = Int(text[range].replacingOccurrences(of: ",", with: "")) else { return false }
            return value % 10 == 0
        }
    }

    @Test func textRoundsAmountsAndHidesAccountNumbers() {
        let text = "You spend £47.99 a month and £1,234 on rent. Account 12345678, sort code 12-34-56. Lost -£16."
        let shown = PresentationFormat.text(text, true)
        #expect(shown == "You spend £50 a month and £1,200 on rent. Account ••••, sort code ••••. Lost -£20.")
        #expect(PresentationFormat.text(text, false) == text)
        #expect(PresentationFormat.money(1_050, true) == "£1,100")
        #expect(PresentationFormat.money(4.2, true, style: .pence) == "£0")
        #expect(PresentationFormat.merchant("Tesco", true) == "A shop")
        #expect(PresentationFormat.bank("Monzo", true) == "Your bank")
    }

    @Test func testItRoundsEveryAmount() {
        let state = TestItViewModel.makeState(result: TestItFixtures.result, phase: .ready, presentation: true)
        let lines = state.options.flatMap { $0.facts + $0.yearRows.map(\.text) + $0.yearRows.compactMap(\.change) }
            + [state.summary, state.hero?.amountText ?? ""]
        #expect(!lines.isEmpty)
        #expect(lines.allSatisfy(Self.onlyRoundedAmounts))
        #expect(!state.intro.contains(TestItFixtures.result.character.name) || TestItFixtures.result.character.name == "You")
    }

    @Test func decisionRoundsServerText() {
        var state = Fixtures.Decision.ready
        state.headline = "Fix for 5 years and save £193.50 a year"
        state.reasons = ["Your payment is £1,066 a month."]
        let shown = state.presented(true)
        #expect(shown.headline == "Fix for 5 years and save £190 a year")
        #expect(shown.reasons == ["Your payment is £1,100 a month."])
        #expect(state.presented(false) == state)
    }

    @Test func bankHidesProviderName() {
        let state = Fixtures.Bank.connected.presented(true)
        #expect(state.providerName == "Your bank")
    }

    @Test func lessonRoundsHeroAndChange() {
        var state = Fixtures.LessonScreen.unanswered
        state.heroLine = "£695 → £1,150"
        state.changeSentence = "Up £455 from 2021 to 2023."
        let shown = state.presented(true)
        #expect(shown.heroLine == "£700 → £1,200")
        #expect(shown.changeSentence == "Up £460 from 2021 to 2023.")
    }

    @Test func rewindRoundsLinesAndNetWorth() {
        let shown = RewindFixtures.mortgage.presented(true)
        let lines = shown.options.map(\.text) + shown.timeline + shown.didLines + (shown.alternative?.lines ?? [])
        #expect(lines.allSatisfy(Self.onlyRoundedAmounts))
        #expect(shown.options.allSatisfy { $0.netWorth == LLAmountFormat.rounded($0.netWorth) })
        let result = RewindResultViewState(year: 2021, age: 30, abandonedIndex: 100, newIndex: 104, abandonedNetWorth: 71_234, newNetWorth: 75_678, message: "You saved £4,444.")
            .presented(true)
        #expect(result.abandonedNetWorth == 71_200)
        #expect(result.message == "You saved £4,400.")
    }

    @Test func summaryHidesNameAndRounds() {
        let state = SummaryFixtures.fourRibbons
        let shown = state.presented(true)
        #expect(shown.name == "You")
        #expect(!state.name.isEmpty)
        #expect(!shown.title.contains(state.name))
        #expect(!shown.shareText.contains(state.name))
        #expect(Self.onlyRoundedAmounts(shown.shareText))
        #expect(shown.netWorth == LLAmountFormat.rounded(state.netWorth))
    }

    @Test func youHidesNameBankAndRoundsFacts() throws {
        var state = YouFixturesW7.full
        state.personalFacts = ["You spend £47 a month on 6 subscriptions."]
        let shown = state.presented(true)
        #expect(shown.isPresentationMode)
        #expect(shown.profile?.name == "You")
        #expect(shown.personalFacts == ["You spend £50 a month on 6 subscriptions."])
        #expect(shown.bankName == "Your bank")
        let realName = try #require(state.profile?.name)
        #expect(!shown.personaLine.contains(realName) || realName == "You")
        #expect(!state.presented(false).isPresentationMode)
    }
}

/// Lesson chart period and the Life summary Next Move link (milestone 1, V4). W7.
@MainActor
@Suite("Lesson period")
struct LessonPeriodTests {
    static func chart(_ years: ClosedRange<Int>) -> ChartState {
        ChartState(kind: .line, title: "Bank Rate", xLabel: "Year", yLabel: "%",
                   points: years.map { .init(x: Double($0), y: 1, label: nil) }, source: nil)
    }

    @Test func chartUsesTheLessonsOwnPeriod() {
        let shown = LessonViewModel.periodChart(Self.chart(2000...2015), year: 2011)
        #expect(shown.points.map(\.x) == (2002...2011).map(Double.init))
    }

    @Test func chartFromAnotherPeriodIsHidden() {
        let shown = LessonViewModel.periodChart(Self.chart(2006...2008), year: 2021)
        #expect(shown.points.isEmpty)
    }

    @Test func conceptsKeepTheChartAsSent() {
        let chart = Self.chart(2006...2008)
        #expect(LessonViewModel.periodChart(chart, year: nil) == chart)
    }
}
