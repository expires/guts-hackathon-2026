import Foundation
import Testing
@testable import Lifeline

/// Tier 0 ViewModels against MockClient.
@MainActor
@Suite("Core ViewModels with MockClient")
struct CoreViewModelTests {
    private func startedSession(startYear: Int = 2006) async -> GameSession {
        let session = GameSession(client: MockClient())
        let preset = ContractExamples.characters.presets[0]
        let ok = await session.startLife(CharacterChoice(mode: .preset, character: preset).request(startYear: startYear))
        #expect(ok)
        return session
    }

    @Test func contractExamplesDecode() {
        #expect(ContractExamples.characters.presets.count == 2)
        #expect(ContractExamples.life.id == "lf_8f3a2c")
        #expect(ContractExamples.event.choices.count == 2)
        #expect(ContractExamples.lesson.sentences.count == 2)
        #expect(!ContractExamples.sources.isEmpty)
        #expect(ContractExamples.sources[0].fetchedAt != nil)
    }

    @Test func characterSelectOrderAndRoutes() async {
        let session = GameSession(client: MockClient())
        let model = CharacterSelectViewModel(session: session)
        var routes: [CharacterSelectViewModel.Route] = []
        model.onRoute = { routes.append($0) }
        await model.load()
        let state = model.state
        #expect(state.phase == .ready)
        #expect(state.cards.first?.kind == .playYourself)
        #expect(state.cards.last?.kind == .godMode)
        #expect(state.cards.last?.isLocked == true)
        #expect(state.cards.map(\.id) == ["self", "preset.nurse-leeds", "preset.banker-london", "random", "god"])
        #expect(state.usesSampleData)

        model.select("god")
        model.select("self")
        model.select("preset.nurse-leeds")
        #expect(routes.count == 3)
        #expect(routes[0] == .store)
        #expect(routes[1] == .form(.playYourself))
        if case let .startYear(choice) = routes[2] {
            #expect(choice.character.id == "nurse-leeds")
        } else {
            Issue.record("Expected startYear route")
        }
    }

    @Test func godModeOpensFormWhenOwned() {
        let session = GameSession(client: MockClient())
        session.ownsGodMode = true
        let model = CharacterSelectViewModel(session: session)
        var route: CharacterSelectViewModel.Route?
        model.onRoute = { route = $0 }
        model.select("god")
        #expect(route == .form(.godMode))
        #expect(model.state.cards.last?.isLocked == false)
    }

    @Test func startYearPickerStartsLife() async {
        let session = GameSession(client: MockClient())
        let choice = CharacterChoice(mode: .preset, character: ContractExamples.characters.presets[0])
        let model = StartYearPickerViewModel(choice: choice, session: session)
        #expect(model.state.selectedYear == 2000)
        #expect(model.state.ageAtStart == 18)
        model.setYear(1985)
        #expect(model.state.selectedYear == 1998, "Clamped to the year the character turns 16")
        model.setYear(2006)
        let ok = await model.start()
        #expect(ok)
        #expect(session.phase == .playing)
        #expect(session.life?.age == 24)
    }

    @Test func lifeAgeEventChooseFlow() async throws {
        let session = await startedSession()
        let life = LifeViewModel(session: session)
        let sheet = EventSheetViewModel(session: session)
        let before = life.state.netWorth
        #expect(life.state.canAge)
        #expect(sheet.state == nil)

        await session.age()
        #expect(life.state.header.age == 25)
        #expect(life.state.ageCount == 1)
        #expect(!life.state.canAge)
        #expect(life.state.ageHint == "Answer the open event first.")
        let event = try #require(sheet.state)
        #expect(event.title == "Your rent is going up")
        #expect(event.sources.first?.status == .cached)
        #expect(event.sources.first?.note == "UK average used")

        await session.age()
        #expect(life.state.header.age == 25, "AGE must not run while an event is open")

        await session.choose(choiceID: "move", eventID: event.id)
        #expect(sheet.state == nil)
        #expect(life.state.canAge)
        #expect(life.state.netWorth == before - 600)
        #expect(life.state.outcome?.changes.contains("-£600") == true)
        #expect(life.state.history.count == 2)
        #expect(life.state.canRewind)
        #expect(session.pendingLesson?.conceptId == "inflation")
    }

    @Test func defaultChoiceUsesContractExample() async throws {
        let session = await startedSession()
        let before = try #require(session.life?.finances.netWorth)
        await session.age()
        let event = try #require(session.activeEvent)
        await session.choose(choiceID: "accept", eventID: event.id)
        #expect(session.life?.finances.netWorth == before - 540)
        #expect(session.lastOutcome?.good == false)
    }

    @Test func newLifeReturnsToSelect() async {
        let session = await startedSession()
        let model = LifeViewModel(session: session)
        model.actions.onNewLife()
        #expect(session.phase == .selecting)
        #expect(session.life == nil)
    }

    @Test func unknownPresetShowsError() async {
        let session = GameSession(client: MockClient())
        let ok = await session.startLife(.init(mode: .preset, startYear: 2006, presetId: "nope"))
        #expect(!ok)
        #expect(session.errorMessage == "That character does not exist.")
        #expect(session.phase == .selecting)
    }

    @Test func characterFormValidatesAndBuildsChoice() {
        let model = CharacterFormViewModel(mode: .playYourself)
        #expect(!model.state.canContinue)
        var fields = model.state.fields
        fields.occupation = "nurse"
        fields.town = "Leeds"
        fields.income = -5
        model.update(fields)
        #expect(model.state.canContinue)
        #expect(model.state.fields.income == 0)
        var choice: CharacterChoice?
        model.onContinue = { choice = $0 }
        model.actions.onContinue()
        #expect(choice?.mode == ._self)
        #expect(choice?.character.town == "Leeds")
    }

    @Test func bankProfilePrefillsForm() {
        let model = CharacterFormViewModel(mode: .playYourself)
        model.apply(bankProfile: ContractExamples.bankSummary.profile, status: .mock)
        #expect(model.state.fields.income == 38_000)
        #expect(model.state.fields.housing == .mortgage)
        #expect(model.state.bankStatusText == "Filled from your bank (sample data)")
    }
}

@Suite("Character choice")
struct CharacterChoiceTests {
    @Test func defaultStartYearIsAge18InRange() {
        let amira = ContractExamples.characters.presets[0]
        let choice = CharacterChoice(mode: .preset, character: amira)
        #expect(choice.defaultStartYear == 2000)
        #expect(choice.startYearRange == 1998...2026, "Earliest start is the year Amira (born 1982) turns 16")
    }

    @Test func startYearNeverBeforeAge16() {
        var young = ContractExamples.characters.presets[0]
        young.birthYear = 2005
        let choice = CharacterChoice(mode: ._self, character: young)
        #expect(choice.startYearRange.lowerBound == 2021)
        #expect(choice.defaultStartYear == 2023)
    }

    @Test func startYearRangeAppliesToRandom() {
        var random = ContractExamples.characters.random
        random.birthYear = 1980
        let choice = CharacterChoice(mode: .random, character: random)
        #expect(choice.startYearRange.lowerBound == 1996)
    }

    @Test func oldCharacterStillStartsAt1990() {
        var old = ContractExamples.characters.presets[0]
        old.birthYear = 1940
        #expect(CharacterChoice(mode: .preset, character: old).startYearRange.lowerBound == 1990)
    }

    @Test func requestShapes() {
        let amira = ContractExamples.characters.presets[0]
        let preset = CharacterChoice(mode: .preset, character: amira).request(startYear: 2006)
        #expect(preset.presetId == "nurse-leeds")
        #expect(preset.character == nil)

        let random = CharacterChoice(mode: .random, character: ContractExamples.characters.random).request(startYear: 2006)
        #expect(random.seed == 424242)

        let me = CharacterChoice(mode: ._self, character: amira).request(startYear: 2026)
        #expect(me.character?.name == "Amira")
        #expect(me.mode == ._self)
    }
}
