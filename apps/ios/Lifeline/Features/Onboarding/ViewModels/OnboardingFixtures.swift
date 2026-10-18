import Foundation

/// Onboarding fixtures for previews, the Playground and tests (ADR 0069).
/// Numbers come from responses recorded from the local API (`OnboardingRecorded`) and the contract examples.
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

    static var welcome: OnboardingViewState { base(.welcome) }
    static var problem: OnboardingViewState { base(.problem) }
    static var language: OnboardingViewState { base(.language) }

    /// French picked: the language screen redraws in French before Confirm.
    static var languageFrench: OnboardingViewState {
        var state = base(.language)
        state.language = .fr
        return state
    }

    static var features: OnboardingViewState { base(.features) }

    /// "Pick your student" with the sample students (all ADR 0069 card fields).
    static var pickStudent: OnboardingViewState {
        var state = base(.connect)
        state.samples = OnboardingViewModel.sampleCards(OnboardingRecorded.samples.samples)
        return state
    }

    /// Older server: cards without the ADR 0069 fields (rows hide).
    static var pickStudentOldServer: OnboardingViewState {
        var state = base(.connect)
        let samples: [SampleStatement] = ContractExamples.decode(#"""
        [{"id": "scholarship", "title": "Scholarship student", "description": "Scholarship and bursary, about £420 a month, no debt",
          "funding": ["scholarship", "bursary"], "months": 3}]
        """#)
        state.samples = OnboardingViewModel.sampleCards(samples)
        return state
    }

    static var samplesLoading: OnboardingViewState {
        var state = base(.connect)
        state.samplesLoading = true
        return state
    }

    static var signInDemoOnly: OnboardingViewState { base(.signIn) }
    static var signInApple: OnboardingViewState { base(.signIn, appleAvailable: true) }

    static var connectError: OnboardingViewState {
        var state = pickStudent
        state.errorMessage = L10n.tr("This file is larger than 5 MB. Export a shorter period and try again.")
        return state
    }

    /// The recorded responses for the sample student "scottish". The profile period is September, the last
    /// full month before the recorded October.
    static var collected: OnboardingViewModel.Collected {
        let september = OnboardingRecorded.spending("2026-09")
        let payments = OnboardingViewModel.billCategories.compactMap { try? OnboardingRecorded.categoryDetail($0, "2026-09") }
        return .init(
            profile: OnboardingRecorded.profile,
            spending: september,
            currentMonth: OnboardingRecorded.spending.month,
            bills: OnboardingRecorded.bills,
            subscriptions: OnboardingRecorded.subscriptions,
            billPayments: payments,
            overview: OnboardingRecorded.overview,
            sources: nil,
            habits: OnboardingRecorded.habits,
            forecast: OnboardingRecorded.forecast
        )
    }

    static var scottish: SampleStatement? {
        OnboardingRecorded.samples.samples.first { $0.id == "scottish" }
    }

    /// Building, stage 4 of 8 running.
    static var building: OnboardingViewState {
        var state = base(.building)
        state.building.stages = OnboardingViewModel.stages(firstLabel: L10n.tr("Reading the statement"))
        let details = [OnboardingViewModel.importSummary(OnboardingRecorded.importResult), OnboardingViewModel.incomeDetail(sample: scottish, profile: OnboardingRecorded.profile),
                       OnboardingViewModel.spendingTotalText(OnboardingRecorded.spending("2026-09"), currentMonth: OnboardingRecorded.spending.month)]
        for index in 0..<3 {
            state.building.stages[index].status = .done
            state.building.stages[index].detail = details[index]
        }
        state.building.stages[3].status = .running
        return state
    }

    /// Building finished: "View profile" shows. One stage skipped (its call failed).
    static var buildingDone: OnboardingViewState {
        var state = building
        for index in state.building.stages.indices {
            state.building.stages[index].status = .done
        }
        state.building.stages[3].detail = OnboardingViewModel.billsDetail(bills: OnboardingRecorded.bills, subscriptions: OnboardingRecorded.subscriptions)
        state.building.stages[4].detail = L10n.tr("No debts found")
        state.building.stages[5].status = .skipped
        state.building.stages[5].detail = L10n.tr("Not available right now")
        state.building.stages[6].detail = L10n.tr("Habit score \(OnboardingRecorded.habits.overall ?? 0) out of 100")
        state.building.stages[7].detail = L10n.tr("Forecast ready")
        state.building.isFinished = true
        return state
    }

    static var profile: OnboardingViewState {
        var state = base(.profile)
        state.profile = OnboardingViewModel.makeProfile(sample: scottish, collected: collected)
        return state
    }

    /// One "3 things Penny noticed" row open on its evidence.
    static var profileEvidence: OnboardingViewState {
        var state = profile
        state.expandedNoticedID = state.profile?.noticed.first?.id
        return state
    }

    static var howDecides: OnboardingViewState {
        var state = base(.howDecides)
        state.decides = OnboardingViewModel.makeDecides(OnboardingRecorded.forecast)
        return state
    }

    /// Callum (canvas 2): running short.
    static var howDecidesShort: OnboardingViewState {
        var state = base(.howDecides)
        state.decides = OnboardingViewModel.makeDecides(ForecastMock.forecast(ForecastMock.short))
        return state
    }

    static var nextMove: OnboardingViewState {
        var state = base(.nextMove)
        state.forecastCard = .make(OnboardingRecorded.forecast)
        return state
    }

    static var nextMoveShort: OnboardingViewState {
        var state = base(.nextMove)
        state.forecastCard = .make(ForecastMock.forecast(ForecastMock.short))
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

    /// Every state, for the Playground gallery.
    static var all: [(id: String, title: String, state: OnboardingViewState)] {
        [
            ("welcome", "Welcome", welcome),
            ("problem", "Problem", problem),
            ("language", "Language", language),
            ("languageFrench", "Language, French picked", languageFrench),
            ("features", "What you can do", features),
            ("pickStudent", "Pick your student", pickStudent),
            ("pickStudentOld", "Pick your student, older server", pickStudentOldServer),
            ("samplesLoading", "Pick your student, loading", samplesLoading),
            ("connectError", "Pick your student, with an error", connectError),
            ("signInDemo", "Sign in, Apple not set up", signInDemoOnly),
            ("signInApple", "Sign in with Apple", signInApple),
            ("student", "Enter your numbers, student", student),
            ("manual", "Enter your numbers, working", manual),
            ("building", "Building their profile", building),
            ("buildingDone", "Building their profile, done", buildingDone),
            ("profile", "Their profile", profile),
            ("profileEvidence", "Their profile, evidence open", profileEvidence),
            ("howDecides", "How Penny decides", howDecides),
            ("howDecidesShort", "How Penny decides, running short", howDecidesShort),
            ("nextMove", "Their Next Move", nextMove),
            ("nextMoveShort", "Their Next Move, running short", nextMoveShort),
        ]
    }
}
