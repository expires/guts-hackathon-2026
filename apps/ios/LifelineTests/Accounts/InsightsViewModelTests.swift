import Foundation
import Testing
@testable import Lifeline

/// Insights against MockClient: the adaptive window, plain-English mapping and the Money tab card.
@MainActor
@Suite("Insights view model")
struct InsightsViewModelTests {
    @Test func loadsSampleInsightsAndSaysWhenHistoryIsShort() async {
        let model = InsightsViewModel(client: MockClient(), months: 6)
        await model.load()
        let state = model.state
        #expect(state.phase == .ready)
        #expect(state.isSampleData)
        #expect(state.note == "Based on your last 4 months")
        #expect(state.months.map(\.label) == ["Jun", "Jul", "Aug", "Sep"])
        #expect(state.sentences.count >= 3)
        #expect(state.windowText == "June to September 2026")
        #expect(state.categories.first?.label == "Housing")
        #expect(state.subscriptions.count == 2)
        #expect(state.patterns?.weekdays.count == 7)
        #expect(!state.hasNoHistory)
    }

    @Test func fullWindowHasNoNote() async {
        let model = InsightsViewModel(client: MockClient(), months: 3)
        await model.load()
        #expect(model.state.note == nil)
        #expect(model.state.months.count == 3)
    }

    @Test func changingTheWindowReloads() async throws {
        let model = InsightsViewModel(client: MockClient(), months: 6)
        await model.load()
        model.select(months: 3)
        try await Task.sleep(for: .milliseconds(100))
        #expect(model.state.selectedMonths == 3)
        #expect(model.state.months.count == 3)
    }

    @Test func changeChipsOnlyAppearWithAnEarlierPeriod() {
        let none = InsightsViewModel.makeState(insights: SampleInsights.make(months: 6), months: 6, phase: .ready)
        #expect(none.categories.allSatisfy { $0.changeText == nil })
        let some = InsightsViewModel.makeState(insights: SampleInsights.make(months: 2), months: 3, phase: .ready)
        #expect(some.categories.contains { $0.changeText != nil })
    }

    @Test func tooLittleHistoryShowsNothingToCompare() {
        var insights = SampleInsights.make(months: 3)
        insights.windowMonths = 0
        let state = InsightsViewModel.makeState(insights: insights, months: 6, phase: .ready)
        #expect(state.hasNoHistory)
        #expect(state.patterns == nil)
        #expect(InsightsViewModel.teaser(insights) == nil)
    }

    @Test func moneyTabCardShowsLastMonthAndTwoSentences() {
        let teaser = InsightsViewModel.teaser(SampleInsights.make(months: 6))
        #expect(teaser?.monthText == "September")
        #expect(teaser?.spentText == "£1,865")
        #expect(teaser?.earnedText == "£2,480")
        #expect(teaser?.sentences.count == 2)
    }
}
