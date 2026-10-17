import SwiftUI

/// Glue for the Playground scheme (`-playground`). Maps gallery entries to Views with fixtures.
/// The "Full app" entry runs the real flow on `MockClient`.
struct PlaygroundScreen: View {
    @State private var model = GalleryViewModel()
    @State private var appSession = GameSession(client: MockClient())

    var body: some View {
        GalleryView(state: model.state) { id in
            destination(id)
        }
    }

    // swiftlint:disable:next cyclomatic_complexity function_body_length
    @ViewBuilder
    private func destination(_ id: String) -> some View {
        switch id {
        case "app.flow": RootScreen(session: appSession)
        case "money.home": NavigationStack { MoneyHomeView(state: Fixtures.MoneyHome.ready) }
        case "money.live": NavigationStack { MoneyHomeView(state: Fixtures.MoneyHome.connectedLive) }
        case "money.loading": NavigationStack { MoneyHomeView(state: Fixtures.MoneyHome.loading) }
        case "money.offline": NavigationStack { MoneyHomeView(state: Fixtures.MoneyHome.offline) }
        case "accounts.none": AccountsView(state: Fixtures.Accounts.none)
        case "accounts.connected": AccountsView(state: Fixtures.Accounts.connected)
        case "accounts.waiting": AccountsView(state: Fixtures.Accounts.waitingForApproval)
        case "accounts.t212error": AccountsView(state: Fixtures.Accounts.trading212Error)
        case "accounts.loading": AccountsView(state: Fixtures.Accounts.loading)
        case "accounts.error": AccountsView(state: Fixtures.Accounts.error)
        case "investments.sample": InvestmentsView(state: Fixtures.Investments.sample)
        case "investments.live": InvestmentsView(state: Fixtures.Investments.live)
        case "investments.replaying": InvestmentsView(state: Fixtures.Investments.replaying)
        case "investments.loading": InvestmentsView(state: Fixtures.Investments.loading)
        case "investments.error": InvestmentsView(state: Fixtures.Investments.error)
        case "habits.ready": HabitsView(state: Fixtures.Habits.ready)
        case "habits.live": HabitsView(state: Fixtures.Habits.live)
        case "habits.loading": HabitsView(state: Fixtures.Habits.loading)
        case "habits.error": HabitsView(state: Fixtures.Habits.error)
        case "you.ready": NavigationStack { YouView(state: Fixtures.You.ready) }
        case "select.ready": CharacterSelectView(state: Fixtures.CharacterSelect.ready)
        case "select.godOwned": CharacterSelectView(state: Fixtures.CharacterSelect.godModeOwned)
        case "select.loading": CharacterSelectView(state: Fixtures.CharacterSelect.loading)
        case "select.offline": CharacterSelectView(state: Fixtures.CharacterSelect.offline)
        case "form.self": CharacterFormView(state: Fixtures.CharacterForm.playYourself)
        case "form.bank": CharacterFormView(state: Fixtures.CharacterForm.bankFilled)
        case "form.god": CharacterFormView(state: Fixtures.CharacterForm.godMode)
        case "year.preset": StartYearPickerView(state: Fixtures.StartYear.preset)
        case "year.starting": StartYearPickerView(state: Fixtures.StartYear.starting)
        case "life.new": LifeView(state: Fixtures.LifeScreen.newLife)
        case "life.mid": LifeView(state: Fixtures.LifeScreen.midLife)
        case "life.event": LifeView(state: Fixtures.LifeScreen.eventOpen)
        case "life.bad": LifeView(state: Fixtures.LifeScreen.badOutcome)
        case "life.dead": LifeView(state: Fixtures.LifeScreen.dead)
        case "event.rent": EventSheetView(state: Fixtures.Event.rentRise)
        case "event.crisis": EventSheetView(state: Fixtures.Event.crisis)
        case "event.submitting": EventSheetView(state: Fixtures.Event.submitting)
        case "activities.list": ActivitiesSheetView(state: Fixtures.Activities.list)
        case "activities.empty": ActivitiesSheetView(state: Fixtures.Activities.empty)
        case "job.normal": JobTabView(state: Fixtures.Tabs.job)
        case "job.risk": JobTabView(state: Fixtures.Tabs.jobAtRisk)
        case "job.none": JobTabView(state: Fixtures.Tabs.noJob)
        case "assets.mid": AssetsTabView(state: Fixtures.Tabs.assets)
        case "assets.empty": AssetsTabView(state: Fixtures.Tabs.assetsEmpty)
        case "people.mid": PeopleTabView(state: Fixtures.Tabs.people)
        case "money.mid": MoneyTabView(state: Fixtures.Tabs.money)
        case "money.new": MoneyTabView(state: Fixtures.Tabs.moneyNewLife)
        case "lesson.new": LessonView(state: Fixtures.LessonScreen.unanswered)
        case "lesson.correct": LessonView(state: Fixtures.LessonScreen.correct)
        case "lesson.wrong": LessonView(state: Fixtures.LessonScreen.wrong)
        case "concepts.ready": ConceptCollectionView(state: Fixtures.Concepts.someUnlocked)
        case "concepts.loading": ConceptCollectionView(state: Fixtures.Concepts.loading)
        case "concepts.error": ConceptCollectionView(state: Fixtures.Concepts.error)
        case "rewind.picker": RewindPickerView(state: Fixtures.Rewind.picker)
        case "rewind.pass": RewindPickerView(state: Fixtures.Rewind.needsPass)
        case "rewind.result": RewindResultView(state: Fixtures.Rewind.result)
        case "summary.death": LifeSummaryView(state: Fixtures.Summary.death)
        case "summary.loading": LifeSummaryView(state: Fixtures.Summary.loading)
        case "summary.error": LifeSummaryView(state: Fixtures.Summary.error)
        case "room.entry": RoomLobbyView(state: Fixtures.Rooms.entry)
        case "room.lobby": RoomLobbyView(state: Fixtures.Rooms.lobbyFour)
        case "room.joining": RoomLobbyView(state: Fixtures.Rooms.joining)
        case "room.rivals": RivalStripView(state: Fixtures.Rooms.rivals)
        case "room.result": RoomResultView(state: Fixtures.Rooms.result)
        case "decision.ready": RealLifeDecisionView(state: Fixtures.Decision.ready)
        case "decision.loading": RealLifeDecisionView(state: Fixtures.Decision.loading)
        case "decision.error": RealLifeDecisionView(state: Fixtures.Decision.error)
        case "store.fresh": StoreView(state: Fixtures.Store.fresh)
        case "store.purchasing": StoreView(state: Fixtures.Store.purchasing)
        case "store.owned": StoreView(state: Fixtures.Store.owned)
        case "bank.intro": BankConnectView(state: Fixtures.Bank.intro)
        case "bank.connecting": BankConnectView(state: Fixtures.Bank.connecting)
        case "bank.connected": BankConnectView(state: Fixtures.Bank.connected)
        case "bank.failed": BankConnectView(state: Fixtures.Bank.failed)
        case "sources.ready": SourcesView(state: Fixtures.Sources.ready)
        case "sources.loading": SourcesView(state: Fixtures.Sources.loading)
        case "sources.error": SourcesView(state: Fixtures.Sources.error)
        case "debug.live": DebugMenuView(state: Fixtures.Debug.live)
        case "debug.presenter": DebugMenuView(state: Fixtures.Debug.presenter)
        case "common.error": ErrorStateView(state: Fixtures.networkError)
        case "common.startAge": ErrorStateView(state: Fixtures.startAgeError)
        case "common.loading": LoadingStateView(state: Fixtures.loading)
        default: Text("No screen for \(id)")
        }
    }
}
