import Foundation
import Testing
@testable import Lifeline

/// Tier 1 and Tier 2 ViewModels against MockClient.
@MainActor
@Suite("Feature ViewModels with MockClient")
struct FeatureViewModelTests {
    private func playedSession() async throws -> GameSession {
        let session = GameSession(client: MockClient())
        _ = await session.startLife(CharacterChoice(mode: .preset, character: ContractExamples.characters.presets[0]).request(startYear: 2006))
        await session.age()
        let event = try #require(session.activeEvent)
        await session.choose(choiceID: "move", eventID: event.id)
        return session
    }

    @Test func lessonQuizAnswersOnce() {
        let model = LessonViewModel(lesson: ContractExamples.lesson, isNewConcept: true)
        #expect(model.state.sentences.count == 2)
        #expect(model.state.chart.points.count == 3)
        #expect(model.state.chart.source?.status == .cached)
        model.actions.onAnswer(1)
        #expect(model.state.quiz.isCorrect)
        model.actions.onAnswer(0)
        #expect(model.state.quiz.selectedIndex == 1, "First answer is final")
    }

    @Test func conceptsLoadAndOpenLesson() async {
        let model = ConceptCollectionViewModel(client: MockClient(), unlockedIDs: ["inflation"])
        await model.load()
        #expect(model.state.phase == .ready)
        #expect(model.state.unlockedCount == 1)
        model.actions.onSelect("inflation")
        #expect(model.selectedLesson?.conceptId == "inflation")
    }

    @Test func rewindUsesFreeRewindThenNeedsPass() async throws {
        let session = try await playedSession()
        let model = RewindViewModel(session: session)
        let picker = model.pickerState
        #expect(picker.options.count == 1)
        #expect(picker.allowanceText == "1 free rewind left")
        #expect(!picker.needsPass)
        await model.rewind(to: picker.options[0].id)
        let result = try #require(model.result)
        #expect(result.abandonedNetWorth == ContractExamples.life.finances.netWorth - 600)
        #expect(session.activeEvent != nil, "The rewound decision is open again")
        #expect(model.pickerState.needsPass)
    }

    @Test func rewindPassAllowsMore() async throws {
        let session = try await playedSession()
        session.hasRewindPass = true
        #expect(RewindViewModel(session: session).pickerState.allowanceText == "Rewind Pass: unlimited rewinds")
    }

    @Test func summaryLoads() async throws {
        let session = try await playedSession()
        let model = LifeSummaryViewModel(client: session.client, lifeID: session.life!.id, emoji: "👩🏽‍⚕️")
        await model.load()
        #expect(model.state.phase == .ready)
        #expect(model.state.name == "Amira")
        #expect(model.state.timeline.count == 2)
    }

    @Test func tabsShowActionsAndAct() async throws {
        let session = try await playedSession()
        let money = MoneyTabViewModel(session: session)
        #expect(money.state.actions.map(\.id) == ["open_isa"])
        #expect(money.state.owe.contains { $0.id == "studentLoan" })
        let before = money.state.netWorth
        money.actions.onAction("open_isa")
        try await Task.sleep(for: .milliseconds(50))
        #expect(money.state.netWorth == before - 600)
        #expect(money.state.outcome?.text == "You opened a savings account.")
        #expect(JobTabViewModel(session: session).state.job?.title == "Nurse")
        #expect(AssetsTabViewModel(session: session).state.items.first?.emoji == "🧓")
        #expect(PeopleTabViewModel(session: session).state.people.first?.name == "Mum")
        #expect(ActivitiesViewModel(session: session).state.actions.isEmpty)
    }

    @Test func sourcesShowStatus() async {
        let model = SourcesViewModel(client: MockClient())
        await model.load()
        #expect(model.state.rows.map(\.status).contains(.mock))
        #expect(model.state.usesSampleData)
    }

    @Test func storePurchaseSetsEntitlement() async {
        let session = GameSession(client: MockClient())
        let model = StoreViewModel(session: session)
        #expect(model.state.demoLabel == "Demo payment")
        await model.buy("lifeline.godmode")
        #expect(session.ownsGodMode)
        #expect(model.state.products.first { $0.id == "lifeline.godmode" }?.isOwned == true)
        await model.buy("lifeline.rewindpass")
        #expect(session.hasRewindPass)
    }

    @Test func bankConnectsWithMockProvider() async {
        let model = BankConnectViewModel(client: MockClient())
        var profile: DecisionProfile?
        model.onUseProfile = { value, _ in profile = value }
        await model.connect()
        #expect(model.state.step == .connected)
        #expect(model.state.status == .mock)
        #expect(model.state.summary?.accounts == 2)
        model.actions.onUseProfile()
        #expect(profile?.annualIncome == 38_000)
    }

    @Test func decisionLoads() async {
        let model = RealLifeDecisionViewModel(client: MockClient(), profile: ContractExamples.decisionProfile, lifeID: nil)
        await model.load()
        #expect(model.state.headline == "Fix for 5 years.")
        #expect(model.state.alternatives.first?.label == "Fix for 2 years")
        #expect(model.state.sources.count == 3)
    }

    @Test func roomLobbyCreatesAndJoins() async {
        let model = RoomLobbyViewModel(client: MockClient(), playerName: "Ash")
        await model.create(mode: "group")
        #expect(model.state.room?.players.first?.isMe == true)
        #expect(model.state.isHost)
        #expect(model.state.canStart)
        let joiner = RoomLobbyViewModel(client: MockClient(), playerName: "Priya")
        joiner.actions.onJoinCodeChange("k7q2zp!")
        #expect(joiner.state.joinCode == "K7Q2ZP")
        await joiner.join()
        #expect(joiner.state.room?.code == "K7Q2ZP")
        #expect(!joiner.state.isHost)
    }

    @Test func fixturesBuild() {
        #expect(Fixtures.CharacterSelect.ready.cards.count == 5)
        #expect(Fixtures.LifeScreen.midLife.header.age == 45)
        #expect(Fixtures.LifeScreen.dead.showsSummary)
        #expect(Fixtures.Event.crisis.isAIText)
        #expect(Fixtures.Event.crisis.sources.map(\.status) == [.mock, .cached])
        #expect(Fixtures.Rooms.rivals.rivals.count == 4)
        #expect(Fixtures.Rooms.lobbyFour.room?.players.count == 4)
        #expect(Fixtures.Summary.death.died == 2061)
        #expect(Fixtures.Rewind.needsPass.needsPass)
        #expect(Fixtures.Decision.ready.successRate == 0.7)
        #expect(Fixtures.Bank.connected.summary != nil)
        #expect(Fixtures.Sources.ready.rows.count == 3)
        #expect(Fixtures.Tabs.money.mortgageNote == "Mortgage rate 4.49%, fixed until 2030")
        #expect(GalleryViewModel.catalog.sections.flatMap(\.entries).count > 50)
    }
}
