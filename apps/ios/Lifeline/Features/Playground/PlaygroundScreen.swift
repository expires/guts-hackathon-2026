import SwiftUI

/// Glue for the Playground scheme (`-playground`). Maps gallery entries to Views with fixtures.
/// The "Full app" entry runs the real flow on `MockClient`.
struct PlaygroundScreen: View {
    @State private var model = GalleryViewModel()
    @State private var appSession = GameSession(client: MockClient(data: .recorded))

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
        case "penny.live":
            PennyScreen(
                service: PennyFixtures.scripted(events: PennyFixtures.answerEvents, fallback: PennyFixtures.answerResponse, gap: .milliseconds(400)),
                onClose: {}
            )
        case let penny where penny.hasPrefix("penny."):
            if let entry = PennyFixtures.all.first(where: { $0.id == penny }) {
                LLSheetFrame { PennyChatView(state: entry.state) }
            }
        case let rooms where rooms.hasPrefix("w9rooms."): RoomsPlayground.view(rooms)
        case "money.habits.score": HabitsPanelView(state: HabitsPanelFixtures.score).padding().paperBackground()
        case "money.habits.sample": HabitsPanelView(state: HabitsPanelFixtures.sample).padding().paperBackground()
        case "money.habits.empty": HabitsPanelView(state: .empty).padding().paperBackground()
        case "money.ready": MoneyHomeView(state: Fixtures.MoneyHome.ready).previewInNavigation()
        case "money.noData": MoneyHomeView(state: Fixtures.MoneyHome.noData).previewInNavigation()
        case "money.rateLimited": MoneyHomeView(state: Fixtures.MoneyHome.rateLimited).previewInNavigation()
        case "money.offline": MoneyHomeView(state: Fixtures.MoneyHome.offline).previewInNavigation()
        case "onboarding.flow": OnboardingScreen(client: appSession.client) {}
        case "account.flow": AccountScreen(client: appSession.client)
        case let onboarding where onboarding.hasPrefix("onboarding."):
            if let entry = OnboardingFixtures.all.first(where: { "onboarding." + $0.id == onboarding }) {
                OnboardingView(state: entry.state)
            }
        case let account where account.hasPrefix("account."):
            if let entry = AccountFixtures.all.first(where: { "account." + $0.id == account }) {
                AccountView(state: entry.state)
            }
        case "select.ready": CharacterSelectView(state: Fixtures.CharacterSelect.ready)
        case "select.loading": CharacterSelectView(state: Fixtures.CharacterSelect.loading)
        case "select.offline": CharacterSelectView(state: Fixtures.CharacterSelect.offline)
        case "form.self": CharacterFormView(state: Fixtures.CharacterForm.playYourself)
        case "form.bank": CharacterFormView(state: Fixtures.CharacterForm.bankFilled)
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
        case "bank.intro": BankConnectView(state: Fixtures.Bank.intro)
        case "bank.connecting": BankConnectView(state: Fixtures.Bank.connecting)
        case "bank.connected": BankConnectView(state: Fixtures.Bank.connected)
        case "bank.failed": BankConnectView(state: Fixtures.Bank.failed)
        case "sources.ready": SourcesView(state: Fixtures.Sources.ready)
        case "sources.loading": SourcesView(state: Fixtures.Sources.loading)
        case "sources.error": SourcesView(state: Fixtures.Sources.error)
        case "debug.live": DebugMenuView(state: Fixtures.Debug.live)
        case "debug.presenter": DebugMenuView(state: Fixtures.Debug.presenter)
        // Money tab (ADR 0016, 0017, 0018)
        case "money.home.ready": MoneyHomeView(state: Fixtures.MoneyHome.ready).previewInNavigation()
        case "money.home.revealed": MoneyHomeView(state: Fixtures.MoneyHome.revealed).previewInNavigation()
        case "money.home.loading": MoneyHomeView(state: Fixtures.MoneyHome.loading).previewInNavigation()
        case "money.home.offline": MoneyHomeView(state: Fixtures.MoneyHome.offline).previewInNavigation()
        case "nextMove.ready": card(NextMoveCardView(state: Fixtures.NextMove.ready))
        case "nextMove.inPlan": card(NextMoveCardView(state: Fixtures.NextMove.inPlan))
        case "nextMove.adding": card(NextMoveCardView(state: Fixtures.NextMove.adding))
        case "nextMove.runnerUp": card(NextMoveCardView(state: Fixtures.NextMove.focusedRunnerUp))
        case "nextMove.live": card(NextMoveCardView(state: Fixtures.NextMove.liveUntestable))
        case "nextMove.loading": card(NextMoveCardView(state: Fixtures.NextMove.loading))
        case "nextMove.error": card(NextMoveCardView(state: Fixtures.NextMove.error))
        case "why.mortgage": NextMoveWhyView(state: Fixtures.Why.mortgage, onTestIt: {})
        case "why.noLesson": NextMoveWhyView(state: Fixtures.Why.noLesson)
        case "why.withLesson": NextMoveWhyView(state: Fixtures.Why.withLesson)
        case "why.loading": NextMoveWhyView(state: Fixtures.Why.loadingLesson)
        case "why.error": NextMoveWhyView(state: Fixtures.Why.lessonError)
        case "plan.one": PlanView(state: Fixtures.Plan.oneItem)
        case "plan.empty": PlanView(state: Fixtures.Plan.empty)
        case "plan.loading": PlanView(state: Fixtures.Plan.loading)
        case "plan.error": PlanView(state: Fixtures.Plan.error)
        case "widgets.ready": card(MoneyWidgetsView(state: Fixtures.Widgets.ready))
        case "widgets.partial": card(MoneyWidgetsView(state: Fixtures.Widgets.partialError))
        case "widgets.empty": card(MoneyWidgetsView(state: Fixtures.Widgets.empty))
        case "widgets.loading": card(MoneyWidgetsView(state: Fixtures.Widgets.loading))
        case "guess.before": GuessSpendView(state: Fixtures.Guess.beforeGuess)
        case "guess.revealed": GuessSpendView(state: Fixtures.Guess.revealed)
        case "guess.past": GuessSpendView(state: Fixtures.Guess.pastDay)
        case "guess.submitting": GuessSpendView(state: Fixtures.Guess.submitting)
        case "guess.invalid": GuessSpendView(state: Fixtures.Guess.invalidEntry)
        case "guess.loading": GuessSpendView(state: Fixtures.Guess.loading)
        case "guess.error": GuessSpendView(state: Fixtures.Guess.error)
        case "accuracy.ready": SpendAccuracyView(state: Fixtures.SpendAccuracy.ready)
        case "accuracy.loading": SpendAccuracyView(state: Fixtures.SpendAccuracy.loading)
        case "accuracy.error": SpendAccuracyView(state: Fixtures.SpendAccuracy.error)
        // Play and You tabs
        case "profile.picker.none": ProfilePickerView(state: ProfilePickerPreviews.nothingActive)
        case "profile.picker.sample": ProfilePickerView(state: ProfilePickerPreviews.sampleActive)
        case "profile.picker.you": ProfilePickerView(state: ProfilePickerPreviews.youActive)
        case "profile.connect.none": ConnectionsView(state: ConnectionsPreviews.nothing)
        case "profile.connect.both": ConnectionsView(state: ConnectionsPreviews.connected)
        case "profile.connect.continue": ConnectionsView(state: ConnectionsPreviews.withContinue)
        case "profile.connect.confirm": ConnectionsView(state: ConnectionsPreviews.confirming)
        case "profile.stats.none": ProfileStatsView(state: ProfileStatsPreviews.nothing)
        case "profile.stats.t212": ProfileStatsView(state: ProfileStatsPreviews.t212Only)
        case "profile.stats.full": ProfileStatsView(state: ProfileStatsPreviews.full)
        case "profile.stats.sample": ProfileStatsView(state: ProfileStatsPreviews.sample)
        case "profile.flow": PlayAsYourselfFlowScreen(session: appSession, start: .picker) {}
        case "play.ready": PlayView(state: Fixtures.Play.ready).previewInNavigation()
        case "play.noLives": PlayView(state: Fixtures.Play.noLives).previewInNavigation()
        case "play.loading": PlayView(state: Fixtures.Play.loading).previewInNavigation()
        case "play.error": PlayView(state: Fixtures.Play.error).previewInNavigation()
        case "you.ready": YouView(state: Fixtures.You.ready).previewInNavigation()
        case "you.release": YouView(state: Fixtures.You.release).previewInNavigation()
        case "you.loading": YouView(state: Fixtures.You.loading).previewInNavigation()
        case "you.error": YouView(state: Fixtures.You.error).previewInNavigation()
        case "evaluation.ready": EvaluationView(state: Fixtures.Evaluation.ready)
        case "evaluation.loading": EvaluationView(state: Fixtures.Evaluation.loading)
        case "evaluation.error": EvaluationView(state: Fixtures.Evaluation.error)
        case "lifeMenu.mid": LifeMenuBarView(state: Fixtures.LifeMenu.midLife)
        case "lifeMenu.dead": LifeMenuBarView(state: Fixtures.LifeMenu.dead)
        case let w7 where w7.hasPrefix("w7lesson."):
            if let entry = LessonFixtures.all.first(where: { "w7lesson." + $0.id == w7 }) { LessonView(state: entry.state) }
        case let w7 where w7.hasPrefix("w7rewind."):
            if let entry = RewindFixtures.all.first(where: { "w7rewind." + $0.id == w7 }) { RewindPickerView(state: entry.state) }
        case let w7 where w7.hasPrefix("w7summary."):
            if let entry = SummaryFixtures.all.first(where: { "w7summary." + $0.id == w7 }) { LifeSummaryView(state: entry.state) }
        case "w7rooms.lobby": RoomLobbyView(state: RoomsFixtures.lobby)
        case "w7rooms.live": RoomLiveView(state: RoomsFixtures.live)
        case "w7rooms.result": RoomResultView(state: RoomsFixtures.result)
        case "w7play.withRoom": PlayView(state: PlayFixturesW7.withRoom).previewInNavigation()
        case "w7you.full": YouView(state: YouFixturesW7.full).previewInNavigation()
        case let testIt where testIt.hasPrefix("testit."):
            if let entry = TestItFixtures.all.first(where: { $0.id == testIt }) {
                TestItView(state: entry.state)
            } else {
                Text("No screen for \(id)")
            }
        case "common.error": ErrorStateView(state: Fixtures.networkError)
        case "common.startAge": ErrorStateView(state: Fixtures.startAgeError)
        case "common.loading": LoadingStateView(state: Fixtures.loading)
        default: Text("No screen for \(id)")
        }
    }

    /// A single card in a scroll view, as on the Money tab.
    private func card(_ content: some View) -> some View {
        ScrollView { content.padding() }
    }
}
