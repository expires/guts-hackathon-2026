import Foundation

/// Realistic ViewState values for every screen and state (ADR 0011).
/// Used by `#Preview` blocks and by the Playground gallery. Built from the contract examples
/// through the same mapping code the ViewModels use, plus a few edited copies for other states.
@MainActor
enum Fixtures {
    // MARK: Shared

    static let loading = LoadingViewState(message: "Loading")
    static let networkError = ErrorViewState.from(.network)
    static let serverError = ErrorViewState.from(.server(status: 409, code: "pending_events", message: "Answer the open events before you age.", source: "sim"))
    static let startAgeError = ErrorViewState.from(.server(status: 422, code: "invalid_input", message: "start age must be >= 16", source: "sim"))

    /// One chip per status, with the "UK average used" note.
    static let mockSourceChips: [SourceChipState] = [
        .init(id: "boe.IUMBEDR", name: "Bank of England", status: .live),
        .init(id: "ons.IPHRP", name: "ONS", status: .cached, note: "UK average used"),
        .init(id: "companieshouse.officers", name: "Companies House", status: .mock, note: "Sample numbers. Key not set on the server."),
    ]

    // MARK: Lives used to build states

    static var newLife: Life {
        var life = ContractExamples.lifeReadyToAge
        life.year = 2006
        life.age = 24
        life.history = [.init(year: 2006, age: 24, text: "You start life in Leeds.", netWorth: -12_500, autopilotNetWorth: -12_500, index: 100)]
        life.conceptsUnlocked = []
        return life
    }

    static var midLife: Life {
        var life = ContractExamples.lifeReadyToAge
        life.year = 2027
        life.age = 45
        life.finances.savings = 21_400
        life.finances.investments = 18_900
        life.finances.pension = 61_200
        life.finances.propertyValue = 214_000
        life.finances.mortgageBalance = 121_000
        life.finances.mortgageRate = 4.49
        life.finances.mortgageFixedUntil = 2030
        life.finances.studentLoan = 0
        life.finances.otherDebt = 0
        life.finances.netWorth = 196_000
        life.index.value = 112.6
        life.stats = .init(happiness: 64, health: 71, smarts: 78, money: 69)
        life.assets = [
            .init(id: "as1", kind: .pension, name: "NHS pension", value: 61_200),
            .init(id: "as2", kind: .home, name: "Terraced house, Headingley", value: 214_000),
            .init(id: "as3", kind: .investment, name: "Stocks and shares ISA", value: 18_900),
        ]
        life.relationships += [
            .init(id: "rl2", kind: .spouse, name: "Sam", emoji: "🧑🏻", closeness: 74),
            .init(id: "rl3", kind: .child, name: "Ava", emoji: "👧🏽", closeness: 91),
        ]
        life.availableActions += [
            .init(tab: .assets, id: "remortgage", label: "Look for a new mortgage deal", emoji: "🏦", hint: "Your fix ends in 2030", enabled: true, paid: false),
            .init(tab: .relationships, id: "date_night", label: "Plan a night out", emoji: "🍝", hint: "-£80", enabled: true, paid: false),
            .init(tab: .activities, id: "gym", label: "Join a gym", emoji: "🏋️", hint: "-£35 a month", enabled: true, paid: false),
            .init(tab: .activities, id: "start_business", label: "Start a business", emoji: "🏪", hint: "Boss Mode", enabled: true, paid: true),
        ]
        life.history = [
            .init(year: 2006, age: 24, text: "You start life in Leeds.", netWorth: -12_500, autopilotNetWorth: -12_500, index: 100),
            .init(year: 2008, age: 26, text: "Your rent is going up. You moved to a cheaper flat in Headingley.", decisionId: "ev-2008-1", eventId: "ev-2008-1", choiceId: "move", netWorth: -11_600, autopilotNetWorth: -12_100, index: 101.4),
            .init(year: 2015, age: 33, text: "You bought your first home.", decisionId: "ev-2015-2", eventId: "ev-2015-2", choiceId: "buy", netWorth: 24_000, autopilotNetWorth: 9_800, index: 106.0),
            .init(year: 2022, age: 40, text: "Mortgage rates jumped. You fixed for 5 years.", decisionId: "ev-2022-1", eventId: "ev-2022-1", choiceId: "fix5", netWorth: 141_000, autopilotNetWorth: 118_000, index: 110.2),
        ]
        life.conceptsUnlocked = ["inflation", "compound-interest", "mortgage-fix"]
        return life
    }

    static var deadLife: Life {
        var life = midLife
        life.year = 2061
        life.age = 79
        life.alive = false
        life.causeOfDeath = "Old age"
        return life
    }

    static var crisisEvent: LifeEvent {
        var event = ContractExamples.event
        event.id = "ev-2008-3"
        event.templateId = "employer.insolvent"
        event.area = .employer
        event.emoji = "🏚️"
        event.title = "Your employer has gone bust"
        event.text = "The agency that pays your extra shifts has stopped trading. You lose about £4,200 a year."
        event.textSource = .llm
        event.choices = [
            .init(id: "find_new", label: "Look for new shifts", emoji: "🔎", hint: "3 months on lower pay", isDefault: true),
            .init(id: "use_savings", label: "Use your savings", emoji: "🐖", hint: "-£1,050 from savings", isDefault: false),
            .init(id: "credit_card", label: "Put bills on a credit card", emoji: "💳", hint: "22.9% a year interest", isDefault: false),
        ]
        event.sources = [
            .init(source: "companieshouse", seriesId: "insolvency", status: .mock, note: "Sample numbers. Key not set on the server."),
            .init(source: "nomis", seriesId: "ASHE", status: .cached, note: "UK average used"),
        ]
        return event
    }

    // MARK: Character select

    enum CharacterSelect {
        @MainActor static var ready: CharacterSelectViewState {
            CharacterSelectViewModel.makeState(characters: ContractExamples.characters, phase: .ready, ownsGodMode: false, usesSampleData: true)
        }

        @MainActor static var godModeOwned: CharacterSelectViewState {
            CharacterSelectViewModel.makeState(characters: ContractExamples.characters, phase: .ready, ownsGodMode: true, usesSampleData: false)
        }

        @MainActor static var loading: CharacterSelectViewState {
            CharacterSelectViewModel.makeState(characters: nil, phase: .loading(.init(message: "Loading characters")), ownsGodMode: false, usesSampleData: false)
        }

        @MainActor static var offline: CharacterSelectViewState {
            CharacterSelectViewModel.makeState(characters: nil, phase: .failed(Fixtures.networkError), ownsGodMode: false, usesSampleData: false)
        }
    }

    enum CharacterForm {
        @MainActor static var playYourself: CharacterFormViewState {
            CharacterFormViewModel(mode: .playYourself).state
        }

        @MainActor static var bankFilled: CharacterFormViewState {
            let model = CharacterFormViewModel(mode: .playYourself)
            model.update(.init(name: "Me", emoji: "🙂", birthYear: 1992, occupation: "nurse", regionID: "yorkshire-and-the-humber", town: "Leeds", income: 0, savings: 0, debt: 0, housing: .rent))
            model.apply(bankProfile: ContractExamples.bankSummary.profile, status: .mock)
            return model.state
        }

        @MainActor static var godMode: CharacterFormViewState {
            let model = CharacterFormViewModel(mode: .godMode)
            model.quickPick("banker")
            return model.state
        }
    }

    enum StartYear {
        @MainActor static var preset: StartYearPickerViewState {
            StartYearPickerViewModel.makeState(
                choice: CharacterChoice(mode: .preset, character: ContractExamples.characters.presets[0]),
                year: 2000, isStarting: false, usesSampleData: true
            )
        }

        @MainActor static var starting: StartYearPickerViewState {
            StartYearPickerViewModel.makeState(
                choice: CharacterChoice(mode: .preset, character: ContractExamples.characters.presets[1]),
                year: 2006, isStarting: true, usesSampleData: false
            )
        }
    }

    // MARK: Life

    enum LifeScreen {
        @MainActor static var newLife: LifeViewState {
            LifeViewModel.makeState(life: Fixtures.newLife, outcome: nil, isBusy: false, ageCount: 0, usesSampleData: true, hasRewindPass: false)
        }

        @MainActor static var midLife: LifeViewState {
            LifeViewModel.makeState(life: Fixtures.midLife, outcome: ContractExamples.choiceResult.outcome, isBusy: false, ageCount: 21, usesSampleData: false, hasRewindPass: false)
        }

        @MainActor static var eventOpen: LifeViewState {
            LifeViewModel.makeState(life: ContractExamples.life, outcome: nil, isBusy: false, ageCount: 2, usesSampleData: true, hasRewindPass: false)
        }

        @MainActor static var badOutcome: LifeViewState {
            LifeViewModel.makeState(life: Fixtures.midLife, outcome: ContractExamples.choiceResultDefault.outcome, isBusy: false, ageCount: 21, usesSampleData: false, hasRewindPass: true)
        }

        @MainActor static var dead: LifeViewState {
            LifeViewModel.makeState(life: Fixtures.deadLife, outcome: nil, isBusy: false, ageCount: 55, usesSampleData: false, hasRewindPass: false)
        }
    }

    enum Event {
        @MainActor static var rentRise: EventSheetViewState {
            EventSheetViewModel.makeState(event: ContractExamples.event, isSubmitting: false)
        }

        @MainActor static var crisis: EventSheetViewState {
            EventSheetViewModel.makeState(event: Fixtures.crisisEvent, isSubmitting: false)
        }

        @MainActor static var submitting: EventSheetViewState {
            EventSheetViewModel.makeState(event: ContractExamples.event, isSubmitting: true)
        }
    }

    enum Activities {
        @MainActor static var list: ActivitiesViewState {
            .init(actions: StateMapping.actions(Fixtures.midLife, tab: .activities), isBusy: false, outcome: nil)
        }

        @MainActor static var empty: ActivitiesViewState {
            .init(actions: [], isBusy: false, outcome: nil)
        }
    }

    enum Tabs {
        @MainActor static var job: JobTabViewState {
            JobTabViewModel.makeState(life: Fixtures.midLife, isBusy: false, outcome: nil)
        }

        @MainActor static var jobAtRisk: JobTabViewState {
            var life = Fixtures.midLife
            life.job?.employerStatus = .insolvent
            return JobTabViewModel.makeState(life: life, isBusy: false, outcome: StateMapping.outcome(ContractExamples.actionResult.outcome))
        }

        @MainActor static var noJob: JobTabViewState {
            var life = Fixtures.midLife
            life.job = nil
            return JobTabViewModel.makeState(life: life, isBusy: false, outcome: nil)
        }

        @MainActor static var assets: AssetsTabViewState {
            AssetsTabViewModel.makeState(life: Fixtures.midLife, isBusy: false, outcome: nil)
        }

        @MainActor static var assetsEmpty: AssetsTabViewState {
            var life = Fixtures.newLife
            life.assets = []
            return AssetsTabViewModel.makeState(life: life, isBusy: false, outcome: nil)
        }

        @MainActor static var people: PeopleTabViewState {
            PeopleTabViewModel.makeState(life: Fixtures.midLife, isBusy: false, outcome: nil)
        }

        @MainActor static var money: MoneyTabViewState {
            MoneyTabViewModel.makeState(life: Fixtures.midLife, isBusy: false, outcome: nil)
        }

        @MainActor static var moneyNewLife: MoneyTabViewState {
            MoneyTabViewModel.makeState(life: Fixtures.newLife, isBusy: false, outcome: StateMapping.outcome(ContractExamples.actionResult.outcome))
        }
    }

    // MARK: Learn

    enum LessonScreen {
        @MainActor static var unanswered: LessonViewState {
            LessonViewModel.makeState(lesson: ContractExamples.lesson, isNewConcept: true, selectedIndex: nil)
        }

        @MainActor static var correct: LessonViewState {
            LessonViewModel.makeState(lesson: ContractExamples.lesson, isNewConcept: true, selectedIndex: ContractExamples.lesson.quiz.answerIndex)
        }

        @MainActor static var wrong: LessonViewState {
            LessonViewModel.makeState(lesson: ContractExamples.lesson, isNewConcept: false, selectedIndex: 0)
        }
    }

    enum Concepts {
        @MainActor static var someUnlocked: ConceptCollectionViewState {
            var concepts = ContractExamples.concepts
            for (id, emoji, title) in [("compound-interest", "🌱", "Compound interest"), ("mortgage-fix", "🔒", "Fixed-rate mortgage"), ("emergency-fund", "🛟", "Emergency fund")] {
                var copy = ContractExamples.concepts[0]
                copy.id = id
                copy.emoji = emoji
                copy.title = title
                concepts.append(copy)
            }
            return ConceptCollectionViewModel.makeState(concepts: concepts, unlocked: ["inflation", "compound-interest"], phase: .ready)
        }

        @MainActor static var loading: ConceptCollectionViewState {
            ConceptCollectionViewModel.makeState(concepts: [], unlocked: [], phase: .loading(.init(message: "Loading concepts")))
        }

        @MainActor static var error: ConceptCollectionViewState {
            ConceptCollectionViewModel.makeState(concepts: [], unlocked: [], phase: .failed(Fixtures.networkError))
        }
    }

    // MARK: Rewind and summary

    enum Rewind {
        @MainActor static var picker: RewindPickerViewState {
            RewindViewModel.makePickerState(life: Fixtures.midLife, hasPass: false, isSubmitting: false)
        }

        @MainActor static var needsPass: RewindPickerViewState {
            var life = Fixtures.midLife
            life.rewind.freeLeft = 0
            return RewindViewModel.makePickerState(life: life, hasPass: false, isSubmitting: false)
        }

        @MainActor static var result: RewindResultViewState {
            RewindViewModel.makeResultState(ContractExamples.rewindResult)
        }
    }

    enum Summary {
        @MainActor static var death: LifeSummaryViewState {
            var summary = ContractExamples.summary
            summary.timeline = Fixtures.midLife.history + [
                .init(year: 2040, age: 58, text: "Paid off the mortgage.", netWorth: 268_000, autopilotNetWorth: 212_000, index: 116),
                .init(year: 2061, age: 79, text: "Died of old age.", netWorth: 312_000, autopilotNetWorth: 241_000, index: 118.5),
            ]
            summary.keyMoments.append(.init(year: 2015, age: 33, emoji: "🏡", text: "Bought a home in Headingley"))
            summary.ribbons.append(.init(id: "saver", title: "Super Saver", emoji: "🐖", reason: "Saved 10% of pay for 20 years"))
            return LifeSummaryViewModel.makeState(summary: summary, emoji: "👩🏽‍⚕️", phase: .ready)
        }

        @MainActor static var loading: LifeSummaryViewState {
            LifeSummaryViewModel.makeState(summary: nil, emoji: "👩🏽‍⚕️", phase: .loading(.init(message: "Adding up your life")))
        }

        @MainActor static var error: LifeSummaryViewState {
            LifeSummaryViewModel.makeState(summary: nil, emoji: "👩🏽‍⚕️", phase: .failed(Fixtures.serverError))
        }
    }

    // MARK: Rooms

    static let fourPlayers: [Components.Schemas.Player] = [
        .init(id: "p1", name: "Ash", isHost: true, lifeId: "lf_room01", age: 31, year: 2026, netWorth: 18_400, index: 104.2, finished: false),
        .init(id: "p2", name: "Priya", isHost: false, lifeId: "lf_room02", age: 33, year: 2028, netWorth: 26_900, index: 109.8, finished: false),
        .init(id: "p3", name: "Tom", isHost: false, lifeId: "lf_room03", age: 29, year: 2024, netWorth: -2_300, index: 96.1, finished: false),
        .init(id: "p4", name: "Mia", isHost: false, lifeId: "lf_room04", age: 79, year: 2074, netWorth: 301_000, index: 117.0, finished: true),
    ]

    enum Rooms {
        @MainActor static var entry: RoomLobbyViewState {
            RoomLobbyViewModel.makeState(room: nil, phase: .ready, joinCode: "K7Q", isHost: false, myName: "Ash")
        }

        @MainActor static var lobbyFour: RoomLobbyViewState {
            var room = ContractExamples.room
            room.mode = .group
            room.maxPlayers = 8
            room.players = Fixtures.fourPlayers.map { .init(id: $0.id, name: $0.name, isHost: $0.isHost, finished: false) }
            return RoomLobbyViewModel.makeState(room: room, phase: .ready, joinCode: "", isHost: true, myName: "Ash")
        }

        @MainActor static var joining: RoomLobbyViewState {
            RoomLobbyViewModel.makeState(room: nil, phase: .loading(.init(message: "Joining room K7Q2ZP")), joinCode: "K7Q2ZP", isHost: false, myName: "Ash")
        }

        @MainActor static var rivals: RivalStripViewState {
            RivalStripViewModel.makeState(players: Fixtures.fourPlayers, myID: "p1")
        }

        static let result = RoomResultViewState(
            rows: [
                .init(id: "p4", rank: 1, name: "Mia", index: 117.0, netWorth: 301_000, ribbons: 4, isMe: false),
                .init(id: "p2", rank: 2, name: "Priya", index: 112.4, netWorth: 244_000, ribbons: 3, isMe: false),
                .init(id: "p1", rank: 3, name: "Ash", index: 108.9, netWorth: 233_500, ribbons: 2, isMe: true),
                .init(id: "p3", rank: 4, name: "Tom", index: 91.3, netWorth: 120_200, ribbons: 1, isMe: false),
            ],
            splits: [
                .init(id: "s1", year: 2008, age: 26, myChoice: "Paid the higher rent", rivalName: "Mia", rivalChoice: "Moved somewhere cheaper"),
                .init(id: "s2", year: 2022, age: 40, myChoice: "Fixed for 2 years", rivalName: "Mia", rivalChoice: "Fixed for 5 years"),
            ],
            winnerName: "Mia"
        )
    }

    // MARK: Decision, store, bank, sources, debug

    enum Decision {
        @MainActor static var ready: RealLifeDecisionViewState {
            RealLifeDecisionViewModel.makeState(decision: ContractExamples.decision, phase: .ready)
        }

        @MainActor static var loading: RealLifeDecisionViewState {
            RealLifeDecisionViewModel.makeState(decision: nil, phase: .loading(.init(message: "Comparing with similar lives")))
        }

        @MainActor static var error: RealLifeDecisionViewState {
            RealLifeDecisionViewModel.makeState(decision: nil, phase: .failed(Fixtures.networkError))
        }
    }

    enum Store {
        @MainActor static var fresh: StoreViewState {
            StoreViewModel.makeState(owned: [], purchasing: nil, message: nil)
        }

        @MainActor static var purchasing: StoreViewState {
            StoreViewModel.makeState(owned: [], purchasing: "lifeline.godmode", message: nil)
        }

        @MainActor static var owned: StoreViewState {
            StoreViewModel.makeState(owned: ["lifeline.rewindpass"], purchasing: nil, message: "Unlocked (Demo payment).")
        }
    }

    enum Bank {
        @MainActor static var intro: BankConnectViewState {
            BankConnectViewModel.makeState(step: .intro, link: nil, summary: nil)
        }

        @MainActor static var connecting: BankConnectViewState {
            BankConnectViewModel.makeState(step: .connecting, link: ContractExamples.bankAuthLink, summary: nil)
        }

        @MainActor static var connected: BankConnectViewState {
            BankConnectViewModel.makeState(step: .connected, link: ContractExamples.bankAuthLink, summary: ContractExamples.bankSummary)
        }

        @MainActor static var failed: BankConnectViewState {
            BankConnectViewModel.makeState(step: .failed(Fixtures.networkError), link: nil, summary: nil)
        }
    }

    enum Sources {
        @MainActor static var ready: SourcesViewState {
            var sources = ContractExamples.sources
            var ons = sources[0]
            ons.id = "ons"
            ons.name = "Office for National Statistics"
            ons.status = .cached
            ons.attribution = "Office for National Statistics"
            ons.licence = "OGL v3.0"
            sources.insert(ons, at: 1)
            return SourcesViewModel.makeState(sources: sources, phase: .ready, usesSampleData: true)
        }

        @MainActor static var loading: SourcesViewState {
            SourcesViewModel.makeState(sources: [], phase: .loading(.init(message: "Checking data sources")), usesSampleData: false)
        }

        @MainActor static var error: SourcesViewState {
            SourcesViewModel.makeState(sources: [], phase: .failed(Fixtures.networkError), usesSampleData: false)
        }
    }

    enum Debug {
        static let live = DebugMenuViewState(
            useMockClient: false,
            activeClient: "live",
            baseURL: "http://localhost:8000",
            demoDeviceID: "",
            activeDeviceID: "3F2A9C1E-7B4D-4E8A",
            demoDeviceIDIsValid: true,
            versionText: "Lifeline 1.0 (1)",
            note: "Changes apply on the next launch. Launch arguments -mockClient, -uiTestingMock and -demoDeviceID always win."
        )

        static let presenter = DebugMenuViewState(
            useMockClient: true,
            activeClient: "mock",
            baseURL: "http://localhost:8000",
            demoDeviceID: "demo-presenter-01",
            activeDeviceID: "demo-presenter-01",
            demoDeviceIDIsValid: true,
            versionText: "Lifeline 1.0 (1)",
            note: "Changes apply on the next launch. Launch arguments -mockClient, -uiTestingMock and -demoDeviceID always win."
        )
    }
}
