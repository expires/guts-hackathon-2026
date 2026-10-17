import Foundation
import Testing
@testable import Lifeline

/// W9: Circles share habit ratios and improvement only (ADR 0052 privacy rule).
@MainActor
@Suite("Circles")
struct CirclesTests {
    @Test func loadsCreatesJoinsAndLeaves() async {
        let model = CirclesViewModel(service: MockPlayService(), isSampleData: true)
        await model.load()
        #expect(model.state.circles.map(\.name) == ["Flat 4B"])

        model.actions.onNameChange("Course mates")
        #expect(model.state.canCreate)
        await model.create()
        #expect(model.state.circles.count == 2)
        #expect(model.state.selectedID != nil)
        #expect(model.state.newName.isEmpty)

        model.actions.onSelect(nil)
        model.actions.onJoinCodeChange("flat4b")
        #expect(model.state.joinCode == "FLAT4B")
        await model.join()
        #expect(model.state.circles.count == 2)
        #expect(model.state.selectedID == "c1")

        await model.leave("c1")
        #expect(model.state.circles.map(\.name) == ["Course mates"])
        #expect(model.state.selectedID == nil)
    }

    @Test func membersRankByImprovementAndShowNoAmounts() throws {
        let state = RoomFlowFixtures.circleDetail
        let circle = try #require(state.circles.first)
        #expect(circle.members.map(\.name) == ["Ava", "You", "Tom", "Jas"])
        #expect(circle.members.map(\.improvementText) == ["+9 points", "+6 points", "+2 points", "-3 points"])
        #expect(circle.recapWeek == "Week 42")
        #expect(circle.members.allSatisfy { $0.habits.count == 6 })
        // Privacy: no text in a circle carries a pound amount.
        let texts = [circle.name, circle.detail, circle.recap ?? ""]
            + circle.members.flatMap { [$0.name, $0.improvementText] + $0.habits.map(\.label) }
        #expect(texts.allSatisfy { !$0.contains("£") })
    }
}
