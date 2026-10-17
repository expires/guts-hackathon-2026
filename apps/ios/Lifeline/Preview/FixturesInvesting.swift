import Foundation

// Fixtures for Accounts, Investments and Habits. Built through the ViewModels' own mapping code.
@MainActor
extension Fixtures {
    @MainActor
    enum Accounts {
        static var none: AccountsViewState {
            AccountsViewModel.makeState(connections: SampleInvesting.connections(), phase: .ready)
        }

        static var connected: AccountsViewState {
            AccountsViewModel.makeState(
                connections: SampleInvesting.connections(monzo: SampleInvesting.monzoConnected, trading212: SampleInvesting.trading212Connected),
                phase: .ready
            )
        }

        /// Monzo signed in; history waits for approval in the Monzo app.
        static var waitingForApproval: AccountsViewState {
            AccountsViewModel.makeState(
                connections: SampleInvesting.connections(monzo: SampleInvesting.monzoWaitingForApproval),
                phase: .ready, monzoGuidanceVisible: true
            )
        }

        /// The Trading212 sheet after Trading212 rejected the key.
        static var trading212Error: AccountsViewState {
            var state = none
            state.trading212Form = .init(
                isSubmitting: false,
                errorText: AccountsViewModel.trading212Message(.server(status: 400, code: "provider_auth", message: "", source: "trading212")),
                guidance: AccountsViewModel.trading212Guidance
            )
            return state
        }

        static var loading: AccountsViewState {
            AccountsViewModel.makeState(connections: nil, phase: .loading(.init(message: AccountsViewModel.loadingMessage)))
        }

        static var error: AccountsViewState {
            AccountsViewModel.makeState(connections: nil, phase: .failed(Fixtures.networkError))
        }
    }

    @MainActor
    enum Investments {
        private static func state(
            _ investments: InvestmentsResponse?, phase: LoadPhase = .ready, replaying: Bool = false
        ) -> InvestmentsViewState {
            let query = IsaBacktestQuery(strategies: InvestmentsViewModel.strategies(
                mixes: InvestmentsViewModel.availableMixes(investments), period: "gfc_2008", isMonthly: true
            ))
            let mixIDs = Set(InvestmentsViewModel.availableMixes(investments).map(\.id))
            return InvestmentsViewModel.makeState(
                investments: investments,
                periods: SampleInvesting.periods,
                phase: phase,
                selectedPeriodID: "gfc_2008",
                selectedMixIDs: mixIDs,
                isMonthly: true,
                backtest: replaying || investments == nil ? nil : .success(SampleInvesting.backtest(query)),
                scenarios: replaying || investments == nil ? nil : .success(SampleInvesting.scenarios(
                    IsaScenariosQuery(strategy: query.strategies[0], horizonMonths: 36)
                )),
                clientKind: .mock
            )
        }

        static var sample: InvestmentsViewState { state(SampleInvesting.investments) }

        static var live: InvestmentsViewState {
            var response = SampleInvesting.investments
            response.meta.dataStatus = .live
            response.meta.label = nil
            return state(response)
        }

        static var replaying: InvestmentsViewState { state(SampleInvesting.investments, replaying: true) }

        static var loading: InvestmentsViewState {
            state(nil, phase: .loading(.init(message: InvestmentsViewModel.loadingMessage)))
        }

        static var error: InvestmentsViewState {
            state(nil, phase: .failed(Fixtures.networkError))
        }
    }

    @MainActor
    enum Habits {
        static var ready: HabitsViewState {
            HabitsViewModel.makeState(habits: SampleInvesting.habits, phase: .ready, isSample: true)
        }

        static var live: HabitsViewState {
            HabitsViewModel.makeState(habits: SampleInvesting.habits, phase: .ready, isSample: false)
        }

        static var loading: HabitsViewState {
            HabitsViewModel.makeState(habits: nil, phase: .loading(.init(message: HabitsViewModel.loadingMessage)), isSample: true)
        }

        static var error: HabitsViewState {
            HabitsViewModel.makeState(habits: nil, phase: .failed(Fixtures.networkError), isSample: true)
        }
    }
}
