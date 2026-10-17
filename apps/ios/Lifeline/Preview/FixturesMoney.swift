import Foundation

// Fixtures for the Money, Play and You tabs and the Life menu (ADR 0016, 0017, 0018).
// Built from the recorded engine output (`PreviewData`) through the ViewModels' own mapping code.
/// Data for previews and the Playground: the recorded engine output for the demo persona
/// (`Preview/Recorded`, real numbers), with contract examples only where no file was recorded.
enum PreviewData {
    static var data: MockData { MockData.recorded }
    static var nextMove: NextMoveResponse { data.nextMove }
    static var financeOverview: FinanceOverview { data.financeOverview }
    static var spending: SpendingResponse { data.spending }
    static var subscriptions: SubscriptionsResponse { data.subscriptions }
    static var bills: BillsResponse { data.bills }
    static var budgets: BudgetsResponse { data.budgets }
    static var goals: GoalsResponse { data.goals }
    static var financeProfile: FinanceProfile { data.financeProfile }
    static var spendPrediction: SpendPrediction { data.spendPrediction }
    static var spendPredictionBeforeGuess: SpendPrediction { data.spendPredictionBeforeGuess }
    static var guesses: GuessesResponse { data.guesses }
    static var predictionEvaluation: PredictionEvaluation { data.predictionEvaluation }

    /// A plan with the recorded top move in it (the recorded plan is empty).
    static var plan: PlanResponse {
        let move = nextMove.top
        let item = PlanItem(
            id: "pl_1",
            moveId: move.id,
            kind: PlanItem.KindPayload(rawValue: move.kind.rawValue) ?? .fixMortgage,
            action: move.action,
            impactPerYear: move.impactPerYear,
            addedAt: ContractExamples.planItem.addedAt,
            status: .todo
        )
        return PlanResponse(items: [item], totalImpactPerYear: item.impactPerYear)
    }
}

@MainActor
extension Fixtures {
    static var allMoves: [Move] { [PreviewData.nextMove.top] + PreviewData.nextMove.runnersUp }

    // MARK: Next Move card

    @MainActor
    enum NextMove {
        static var ready: NextMoveCardState {
            NextMoveViewModel.makeState(response: PreviewData.nextMove, phase: .ready)
        }

        static var inPlan: NextMoveCardState {
            NextMoveViewModel.makeState(
                response: PreviewData.nextMove, phase: .ready,
                plannedMoveIDs: [PreviewData.plan.items[0].moveId],
                planTotal: PreviewData.plan.totalImpactPerYear
            )
        }

        static var adding: NextMoveCardState {
            var state = ready
            state.addingMoveID = PreviewData.nextMove.top.id
            return state
        }

        /// A widget link focused the subscriptions runner-up.
        static var focusedRunnerUp: NextMoveCardState {
            var state = ready
            state.focusedMoveID = PreviewData.nextMove.runnersUp.first?.id
            return state
        }

        /// Live data, no deadline, not testable.
        static var liveUntestable: NextMoveCardState {
            var response = PreviewData.nextMove
            response.meta.dataStatus = .live
            response.meta.label = nil
            response.top = response.runnersUp[0]
            response.runnersUp = []
            response.backtest = nil
            return NextMoveViewModel.makeState(response: response, phase: .ready)
        }

        static var loading: NextMoveCardState {
            NextMoveViewModel.makeState(response: nil, phase: .loading(.init(message: NextMoveViewModel.loadingMessage)))
        }

        static var error: NextMoveCardState {
            NextMoveViewModel.makeState(response: nil, phase: .failed(Fixtures.networkError))
        }
    }

    // MARK: Why?

    @MainActor
    enum Why {
        /// Mortgage move whose concept has no lesson (state for a concept the API does not know).
        static var noLesson: NextMoveWhyViewState {
            var state = NextMoveWhyViewModel.makeState(
                move: PreviewData.nextMove.top, lesson: nil, lessonPhase: .ready, isSampleData: true
            )
            state.hasDecisionDetail = true
            return state
        }

        /// Mortgage move with the contract "fixed-vs-variable" lesson, rate bars and the decision link.
        static var mortgage: NextMoveWhyViewState {
            let move = PreviewData.nextMove.top
            let lesson = PreviewData.data.concepts.first { $0.id == move.conceptId }?.lesson
            var state = NextMoveWhyViewModel.makeState(move: move, lesson: lesson, lessonPhase: .ready, isSampleData: true)
            state.hasDecisionDetail = true
            return state
        }

        /// Subscriptions move with the contract "subscriptions" lesson and its personal sentence.
        static var withLesson: NextMoveWhyViewState {
            let move = PreviewData.nextMove.runnersUp[0]
            var lesson = PreviewData.data.concepts.first { $0.id == move.conceptId }?.lesson ?? ContractExamples.lesson
            if lesson.personal == nil {
                lesson.personal = PreviewData.financeProfile.personalFacts.first { $0.conceptId == move.conceptId }?.text
            }
            return NextMoveWhyViewModel.makeState(
                move: move, lesson: lesson, lessonPhase: .ready, isSampleData: true
            )
        }

        static var loadingLesson: NextMoveWhyViewState {
            NextMoveWhyViewModel.makeState(
                move: PreviewData.nextMove.top, lesson: nil,
                lessonPhase: .loading(.init(message: NextMoveWhyViewModel.loadingMessage)), isSampleData: true
            )
        }

        static var lessonError: NextMoveWhyViewState {
            NextMoveWhyViewModel.makeState(
                move: PreviewData.nextMove.top, lesson: nil, lessonPhase: .failed(Fixtures.networkError), isSampleData: true
            )
        }
    }

    // MARK: Plan

    @MainActor
    enum Plan {
        static var oneItem: PlanViewState {
            PlanViewModel.makeState(plan: PreviewData.plan, phase: .ready, isSampleData: true)
        }

        static var empty: PlanViewState {
            PlanViewModel.makeState(plan: .init(items: [], totalImpactPerYear: 0), phase: .ready, isSampleData: true)
        }

        static var loading: PlanViewState {
            PlanViewModel.makeState(plan: nil, phase: .loading(.init(message: PlanViewModel.loadingMessage)), isSampleData: true)
        }

        static var error: PlanViewState {
            PlanViewModel.makeState(plan: nil, phase: .failed(Fixtures.networkError), isSampleData: false)
        }
    }

    // MARK: Money widgets

    @MainActor
    enum Widgets {
        static var ready: MoneyWidgetsViewState {
            MoneyWidgetsViewModel.makeState(
                overview: .success(PreviewData.financeOverview),
                spending: .success(PreviewData.spending),
                subscriptions: .success(PreviewData.subscriptions),
                bills: .success(PreviewData.bills),
                budgets: .success(PreviewData.budgets),
                goals: .success(PreviewData.goals),
                moves: Fixtures.allMoves
            )
        }

        static var loading: MoneyWidgetsViewState {
            MoneyWidgetsViewModel.makeState(
                overview: nil, spending: nil, subscriptions: nil, bills: nil, budgets: nil, goals: nil, moves: []
            )
        }

        /// Overview and budgets failed; the rest loaded.
        static var partialError: MoneyWidgetsViewState {
            MoneyWidgetsViewModel.makeState(
                overview: .failure(.network),
                spending: .success(PreviewData.spending),
                subscriptions: .success(PreviewData.subscriptions),
                bills: .success(PreviewData.bills),
                budgets: .failure(.server(status: 501, code: "not_implemented", message: "Not built yet.", source: "api")),
                goals: .success(PreviewData.goals),
                moves: Fixtures.allMoves
            )
        }

        /// Empty lists (new account).
        static var empty: MoneyWidgetsViewState {
            var subscriptions = PreviewData.subscriptions
            subscriptions.items = []
            subscriptions.count = 0
            subscriptions.monthlyTotal = 0
            var bills = PreviewData.bills
            bills.items = []
            bills.totalNext30Days = 0
            var budgets = PreviewData.budgets
            budgets.items = []
            var goals = PreviewData.goals
            goals.items = []
            return MoneyWidgetsViewModel.makeState(
                overview: .success(PreviewData.financeOverview),
                spending: .success(PreviewData.spending),
                subscriptions: .success(subscriptions),
                bills: .success(bills),
                budgets: .success(budgets),
                goals: .success(goals),
                moves: []
            )
        }
    }

    // MARK: Guess my spend

    @MainActor
    enum Guess {
        private static var guessesHistory: GuessesResponse { PreviewData.guesses }
        private static var today: String { PreviewData.spendPrediction.date }
        private static var link: MoveLinkState? { MoneyWidgetsViewModel.moveLink(for: .guess, moves: Fixtures.allMoves) }

        /// No guess yet: no prediction in the state.
        static var beforeGuess: GuessSpendViewState {
            GuessSpendViewModel.makeState(
                prediction: PreviewData.spendPredictionBeforeGuess, guesses: guessesHistory, phase: .ready, today: today, moveLink: link
            )
        }

        /// Guess made today (the contract example): prediction, range and reasons shown.
        static var revealed: GuessSpendViewState {
            GuessSpendViewModel.makeState(
                prediction: PreviewData.spendPrediction, guesses: guessesHistory, phase: .ready, today: today, moveLink: link
            )
        }

        /// A past day with its actual, points and beat-the-model.
        static var pastDay: GuessSpendViewState {
            let past = guessesHistory.items[0]
            let backtest = PreviewData.predictionEvaluation.days[0]
            var prediction = PreviewData.spendPredictionBeforeGuess
            prediction.date = past.date
            prediction.predicted = past.predicted
            prediction.low = backtest.low
            prediction.high = backtest.high
            prediction.actual = past.actual
            prediction.reasons = []
            prediction.guess = .init(amount: past.guess, madeAt: "\(past.date)T08:00:00Z", points: past.points, beatModel: past.beatModel)
            return GuessSpendViewModel.makeState(prediction: prediction, guesses: guessesHistory, phase: .ready, today: today)
        }

        static var submitting: GuessSpendViewState {
            var state = beforeGuess
            state.isSubmitting = true
            return state
        }

        static var invalidEntry: GuessSpendViewState {
            var state = beforeGuess
            state.errorMessage = "Enter an amount in pounds, for example 25."
            return state
        }

        static var loading: GuessSpendViewState {
            GuessSpendViewModel.makeState(
                prediction: nil, guesses: nil, phase: .loading(.init(message: GuessSpendViewModel.loadingMessage)), today: nil
            )
        }

        static var error: GuessSpendViewState {
            GuessSpendViewModel.makeState(prediction: nil, guesses: nil, phase: .failed(Fixtures.networkError), today: nil)
        }
    }

    // MARK: Spend model accuracy

    @MainActor
    enum SpendAccuracy {
        static var ready: SpendAccuracyViewState {
            SpendAccuracyViewModel.makeState(evaluation: PreviewData.predictionEvaluation, phase: .ready)
        }

        static var loading: SpendAccuracyViewState {
            SpendAccuracyViewModel.makeState(evaluation: nil, phase: .loading(.init(message: SpendAccuracyViewModel.loadingMessage)))
        }

        static var error: SpendAccuracyViewState {
            SpendAccuracyViewModel.makeState(evaluation: nil, phase: .failed(Fixtures.networkError))
        }
    }

    // MARK: Money tab (whole screen)

    @MainActor
    enum MoneyHome {
        /// Header and payday from the contract examples (morning greeting, profile emoji, days to payday).
        static var header: MoneyHomeViewState.Header {
            MoneyHomeViewModel.header(
                profile: PreviewData.financeProfile,
                now: FinanceMapping.date(PreviewData.spendPrediction.date)!.addingTimeInterval(9 * 3600)
            )
        }

        static var payday: String? { PreviewData.spendPrediction.daysToPayday.map(MoneyHomeViewModel.paydayText) }

        /// Tiles and Coming up from the recorded data (the same numbers `GET /v1/finance/home` returns).
        private static func withMoney(_ state: MoneyHomeViewState) -> MoneyHomeViewState {
            var state = state
            state.content = .ready
            state.tiles = .init(balance: PreviewData.financeOverview.balance, netWorth: PreviewData.financeOverview.netWorth)
            state.comingUp = PreviewData.bills.items.prefix(3).map(MoneyWidgetsViewModel.bill)
            state.comingUpMore = PreviewData.bills.items.count > 3
            state.homeIsSampleData = FinanceMapping.isSample(PreviewData.financeOverview.meta)
            return state
        }

        static var ready: MoneyHomeViewState {
            withMoney(.init(header: header, paydayText: payday, nextMove: NextMove.ready, widgets: Widgets.ready, guess: Guess.beforeGuess))
        }

        static var revealed: MoneyHomeViewState {
            withMoney(.init(header: header, paydayText: payday, nextMove: NextMove.inPlan, widgets: Widgets.ready, guess: Guess.revealed))
        }

        static var loading: MoneyHomeViewState {
            var state = MoneyHomeViewState(nextMove: NextMove.loading, widgets: Widgets.loading, guess: Guess.loading)
            state.content = .loading(.standard)
            return state
        }

        static var offline: MoneyHomeViewState {
            var state = MoneyHomeViewState(nextMove: NextMove.error, widgets: Widgets.partialError, guess: Guess.error)
            state.content = .failed(Fixtures.networkError)
            return state
        }

        /// `has_data` false: one card, "Connect your money".
        static var noData: MoneyHomeViewState {
            var state = MoneyHomeViewState(
                header: MoneyHomeViewModel.header(profile: nil, now: FinanceMapping.date(PreviewData.spendPrediction.date)!.addingTimeInterval(9 * 3600)),
                nextMove: NextMove.loading, widgets: Widgets.loading, guess: Guess.loading
            )
            state.content = .connect(prompt: MoneyHomeViewModel.connectPrompt)
            return state
        }

        /// Rate limited after the client's quiet retry: calm text, pull to refresh.
        static var rateLimited: MoneyHomeViewState {
            var state = MoneyHomeViewState(nextMove: NextMove.loading, widgets: Widgets.loading, guess: Guess.loading)
            state.content = .failed(.from(.server(status: 429, code: "rate_limited", message: "Too many requests", source: "api")))
            return state
        }
    }

    // MARK: Play tab

    @MainActor
    enum Play {
        static var ready: PlayViewState {
            PlayViewModel.makeState(
                lives: ContractExamples.lives.lives, challenges: ContractExamples.challenges,
                conceptsTotal: ContractExamples.concepts.count, phase: .ready,
                current: ContractExamples.life, isSampleData: true, isBusy: false
            )
        }

        static var noLives: PlayViewState {
            PlayViewModel.makeState(
                lives: [], challenges: ContractExamples.challenges, conceptsTotal: ContractExamples.concepts.count,
                phase: .ready, current: nil, isSampleData: true, isBusy: false
            )
        }

        static var loading: PlayViewState {
            PlayViewModel.makeState(
                lives: [], challenges: [], conceptsTotal: 0, phase: .loading(.init(message: PlayViewModel.loadingMessage)),
                current: nil, isSampleData: false, isBusy: false
            )
        }

        static var error: PlayViewState {
            PlayViewModel.makeState(
                lives: [], challenges: [], conceptsTotal: 0, phase: .failed(Fixtures.networkError),
                current: nil, isSampleData: false, isBusy: false
            )
        }
    }

    // MARK: You tab

    @MainActor
    enum You {
        static var ready: YouViewState {
            YouViewModel.makeState(profile: PreviewData.financeProfile, phase: .ready, clientKind: .mock, isDebugBuild: true)
        }

        static var release: YouViewState {
            YouViewModel.makeState(profile: PreviewData.financeProfile, phase: .ready, clientKind: .live, isDebugBuild: false)
        }

        static var loading: YouViewState {
            YouViewModel.makeState(profile: nil, phase: .loading(.init(message: YouViewModel.loadingMessage)), clientKind: .live, isDebugBuild: true)
        }

        static var error: YouViewState {
            YouViewModel.makeState(profile: nil, phase: .failed(Fixtures.networkError), clientKind: .live, isDebugBuild: true)
        }
    }

    // MARK: Decision backtest

    @MainActor
    enum Evaluation {
        static var ready: EvaluationViewState {
            EvaluationViewModel.makeState(evaluation: ContractExamples.evaluation, phase: .ready)
        }

        static var loading: EvaluationViewState {
            EvaluationViewModel.makeState(evaluation: nil, phase: .loading(.init(message: EvaluationViewModel.loadingMessage)))
        }

        static var error: EvaluationViewState {
            EvaluationViewModel.makeState(evaluation: nil, phase: .failed(Fixtures.networkError))
        }
    }

    // MARK: Life menu

    @MainActor
    enum LifeMenu {
        static var midLife: LifeMenuViewState { LifeMenuViewModel.makeState(life: Fixtures.midLife) }
        static var dead: LifeMenuViewState {
            var life = Fixtures.midLife
            life.alive = false
            return LifeMenuViewModel.makeState(life: life)
        }
    }
}
