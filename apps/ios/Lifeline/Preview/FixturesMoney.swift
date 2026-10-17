import Foundation

// Fixtures for the Money, Play and You tabs and the Life menu (ADR 0016, 0017, 0018).
// Built from the contract examples through the ViewModels' own mapping code.
@MainActor
extension Fixtures {
    static var allMoves: [Move] { [ContractExamples.nextMove.top] + ContractExamples.nextMove.runnersUp }

    // MARK: Next Move card

    @MainActor
    enum NextMove {
        static var ready: NextMoveCardState {
            NextMoveViewModel.makeState(response: ContractExamples.nextMove, phase: .ready)
        }

        static var inPlan: NextMoveCardState {
            NextMoveViewModel.makeState(
                response: ContractExamples.nextMove, phase: .ready,
                plannedMoveIDs: [ContractExamples.plan.items[0].moveId],
                planTotal: ContractExamples.plan.totalImpactPerYear
            )
        }

        static var adding: NextMoveCardState {
            var state = ready
            state.addingMoveID = ContractExamples.nextMove.top.id
            return state
        }

        /// A widget link focused the subscriptions runner-up.
        static var focusedRunnerUp: NextMoveCardState {
            var state = ready
            state.focusedMoveID = ContractExamples.nextMove.runnersUp.first?.id
            return state
        }

        /// Live data, no deadline, not testable.
        static var liveUntestable: NextMoveCardState {
            var response = ContractExamples.nextMove
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
                move: ContractExamples.nextMove.top, lesson: nil, lessonPhase: .ready, isSampleData: true
            )
            state.hasDecisionDetail = true
            return state
        }

        /// Mortgage move with the contract "fixed-vs-variable" lesson, rate bars and the decision link.
        static var mortgage: NextMoveWhyViewState {
            let move = ContractExamples.nextMove.top
            let lesson = ContractExamples.concepts.first { $0.id == move.conceptId }?.lesson
            var state = NextMoveWhyViewModel.makeState(move: move, lesson: lesson, lessonPhase: .ready, isSampleData: true)
            state.hasDecisionDetail = true
            return state
        }

        /// Subscriptions move with the contract "subscriptions" lesson and its personal sentence.
        static var withLesson: NextMoveWhyViewState {
            let move = ContractExamples.nextMove.runnersUp[0]
            var lesson = ContractExamples.concepts.first { $0.id == move.conceptId }?.lesson ?? ContractExamples.lesson
            if lesson.personal == nil {
                lesson.personal = ContractExamples.financeProfile.personalFacts.first { $0.conceptId == move.conceptId }?.text
            }
            return NextMoveWhyViewModel.makeState(
                move: move, lesson: lesson, lessonPhase: .ready, isSampleData: true
            )
        }

        static var loadingLesson: NextMoveWhyViewState {
            NextMoveWhyViewModel.makeState(
                move: ContractExamples.nextMove.top, lesson: nil,
                lessonPhase: .loading(.init(message: NextMoveWhyViewModel.loadingMessage)), isSampleData: true
            )
        }

        static var lessonError: NextMoveWhyViewState {
            NextMoveWhyViewModel.makeState(
                move: ContractExamples.nextMove.top, lesson: nil, lessonPhase: .failed(Fixtures.networkError), isSampleData: true
            )
        }
    }

    // MARK: Plan

    @MainActor
    enum Plan {
        static var oneItem: PlanViewState {
            PlanViewModel.makeState(plan: ContractExamples.plan, phase: .ready, isSampleData: true)
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
                overview: .success(ContractExamples.financeOverview),
                spending: .success(ContractExamples.spending),
                subscriptions: .success(ContractExamples.subscriptions),
                bills: .success(ContractExamples.bills),
                budgets: .success(ContractExamples.budgets),
                goals: .success(ContractExamples.goals),
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
                spending: .success(ContractExamples.spending),
                subscriptions: .success(ContractExamples.subscriptions),
                bills: .success(ContractExamples.bills),
                budgets: .failure(.server(status: 501, code: "not_implemented", message: "Not built yet.", source: "api")),
                goals: .success(ContractExamples.goals),
                moves: Fixtures.allMoves
            )
        }

        /// Empty lists (new account).
        static var empty: MoneyWidgetsViewState {
            var subscriptions = ContractExamples.subscriptions
            subscriptions.items = []
            subscriptions.count = 0
            subscriptions.monthlyTotal = 0
            var bills = ContractExamples.bills
            bills.items = []
            bills.totalNext30Days = 0
            var budgets = ContractExamples.budgets
            budgets.items = []
            var goals = ContractExamples.goals
            goals.items = []
            return MoneyWidgetsViewModel.makeState(
                overview: .success(ContractExamples.financeOverview),
                spending: .success(ContractExamples.spending),
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
        private static var guessesHistory: GuessesResponse { ContractExamples.guesses }
        private static var today: String { ContractExamples.spendPrediction.date }
        private static var link: MoveLinkState? { MoneyWidgetsViewModel.moveLink(for: .guess, moves: Fixtures.allMoves) }

        /// No guess yet: no prediction in the state.
        static var beforeGuess: GuessSpendViewState {
            GuessSpendViewModel.makeState(
                prediction: ContractExamples.spendPredictionBeforeGuess, guesses: guessesHistory, phase: .ready, today: today, moveLink: link
            )
        }

        /// Guess made today (the contract example): prediction, range and reasons shown.
        static var revealed: GuessSpendViewState {
            GuessSpendViewModel.makeState(
                prediction: ContractExamples.spendPrediction, guesses: guessesHistory, phase: .ready, today: today, moveLink: link
            )
        }

        /// A past day with its actual, points and beat-the-model.
        static var pastDay: GuessSpendViewState {
            let past = guessesHistory.items[0]
            let backtest = ContractExamples.predictionEvaluation.days[0]
            var prediction = ContractExamples.spendPredictionBeforeGuess
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
            SpendAccuracyViewModel.makeState(evaluation: ContractExamples.predictionEvaluation, phase: .ready)
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
                profile: ContractExamples.financeProfile,
                now: FinanceMapping.date(ContractExamples.spendPrediction.date)!.addingTimeInterval(9 * 3600)
            )
        }

        static var payday: String? { ContractExamples.spendPrediction.daysToPayday.map(MoneyHomeViewModel.paydayText) }

        static var ready: MoneyHomeViewState {
            .init(header: header, paydayText: payday, nextMove: NextMove.ready, widgets: Widgets.ready, guess: Guess.beforeGuess)
        }

        static var revealed: MoneyHomeViewState {
            .init(header: header, paydayText: payday, nextMove: NextMove.inPlan, widgets: Widgets.ready, guess: Guess.revealed)
        }

        static var loading: MoneyHomeViewState {
            .init(nextMove: NextMove.loading, widgets: Widgets.loading, guess: Guess.loading)
        }

        static var offline: MoneyHomeViewState {
            .init(nextMove: NextMove.error, widgets: Widgets.partialError, guess: Guess.error)
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
            YouViewModel.makeState(profile: ContractExamples.financeProfile, phase: .ready, clientKind: .mock, isDebugBuild: true)
        }

        static var release: YouViewState {
            YouViewModel.makeState(profile: ContractExamples.financeProfile, phase: .ready, clientKind: .live, isDebugBuild: false)
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
