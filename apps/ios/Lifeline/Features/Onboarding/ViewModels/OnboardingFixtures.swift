import Foundation

/// Onboarding fixtures for previews, the Playground and tests.
/// Numbers come from the recorded engine output (`PreviewData`) and the contract examples.
@MainActor
enum OnboardingFixtures {
    private static func base(_ step: OnboardingViewState.Step, appleAvailable: Bool = false) -> OnboardingViewState {
        var state = OnboardingViewState(
            signIn: .init(appleAvailable: appleAvailable),
            manual: .init(dealEndYear: 2027, dealEndMonth: 3, dealEndYears: 2026...2036),
            isSampleData: true
        )
        state.step = step
        return state
    }

    static var welcome: OnboardingViewState { base(.welcome(page: 0)) }
    static var welcomeLast: OnboardingViewState { base(.welcome(page: 2)) }
    static var signInDemoOnly: OnboardingViewState { base(.signIn) }
    static var signInApple: OnboardingViewState { base(.signIn, appleAvailable: true) }

    static var connect: OnboardingViewState {
        var state = base(.connect)
        state.signIn.note = "Sign in with Apple is not set up in this build. You use a demo account on this phone."
        return state
    }

    static var connectError: OnboardingViewState {
        var state = base(.connect)
        state.errorMessage = "This file is larger than 5 MB. Export a shorter period and try again."
        return state
    }

    /// The contract example `ManualFinance` (mortgage).
    static var manualMortgage: OnboardingViewState.Manual {
        var manual = base(.manual).manual
        manual.isStudent = false
        manual.age = 34
        manual.postcode = "LS6 1AN"
        manual.housing = .mortgage
        manual.mortgageBalance = 180_000
        manual.mortgageRatePercent = 4.42
        manual.monthlyTakeHome = 2314.18
        manual.savings = 6850
        manual.costs = [.init(id: 1, name: "Council tax", monthlyAmount: 191)]
        manual.locationNote = "Leeds, from your location"
        return manual
    }

    static var manualProblems: OnboardingViewState.Manual {
        var manual = base(.manual).manual
        manual.postcode = "LS6"
        manual.problems = OnboardingViewModel.problems(manual)
        return manual
    }

    /// A student: maintenance loan per term plus part-time pay, an overdraft. Amounts are what a user would type.
    static var manualStudent: OnboardingViewState.Manual {
        var manual = base(.manual).manual
        manual.age = 19
        manual.postcode = "LS6 1AN"
        manual.housing = .rent
        manual.monthlyRent = 520
        manual.loanPlan = .plan5
        if let index = manual.incomes.firstIndex(where: { $0.kind == .maintenanceLoan }) {
            manual.incomes[index].isOn = true
            manual.incomes[index].amount = 1_900
        }
        if let index = manual.incomes.firstIndex(where: { $0.kind == .partTimeJob }) {
            manual.incomes[index].isOn = true
            manual.incomes[index].amount = 380
        }
        if let index = manual.debts.firstIndex(where: { $0.kind == .overdraft }) {
            manual.debts[index].isOn = true
            manual.debts[index].balance = 250
        }
        return manual
    }

    static var samples: OnboardingViewState {
        var state = base(.samples)
        state.samples = OnboardingViewModel.sampleCards(MockExamples.samples)
        return state
    }

    static var samplesLoading: OnboardingViewState {
        var state = base(.samples)
        state.samplesLoading = true
        return state
    }

    static var student: OnboardingViewState {
        var state = base(.manual)
        state.manual = manualStudent
        return state
    }

    static var manual: OnboardingViewState {
        var state = base(.manual)
        state.manual = manualMortgage
        return state
    }

    static var importing: OnboardingViewState {
        var state = base(.importing)
        state.importing = OnboardingViewModel.makeImporting(OnboardingExamples.importResult, shown: 3)
        state.importing.stages[2].done = false
        state.importing.isFinished = false
        return state
    }

    static var reveal: OnboardingViewState {
        var state = base(.reveal)
        state.reveal = OnboardingViewModel.makeReveal(PreviewData.nextMove)
        return state
    }

    static var tips: OnboardingViewState {
        var state = base(.tips)
        state.tips = OnboardingViewModel.makeTips(PreviewData.financeProfile)
        return state
    }

    /// Every state, for the Playground gallery.
    static var all: [(id: String, title: String, state: OnboardingViewState)] {
        [
            ("welcome", "Welcome, page 1", welcome),
            ("welcomeLast", "Welcome, page 3", welcomeLast),
            ("signInDemo", "Sign in, Apple not set up", signInDemoOnly),
            ("signInApple", "Sign in with Apple", signInApple),
            ("connect", "Connect your money", connect),
            ("connectError", "Connect, with an error", connectError),
            ("samples", "Pick a sample student", samples),
            ("samplesLoading", "Sample students, loading", samplesLoading),
            ("student", "Enter your numbers, student", student),
            ("manual", "Enter your numbers, working", manual),
            ("importing", "Importing your history", importing),
            ("reveal", "Next Move reveal", reveal),
            ("tips", "3 tips", tips),
        ]
    }
}
