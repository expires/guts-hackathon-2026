import Foundation
import Testing
@testable import Lifeline

/// Onboarding and account ViewModels (ADR 0029) against closure APIs.
@MainActor
@Suite("Onboarding and account")
struct OnboardingAccountTests {
    private func api(
        bankStatus: String = "mock",
        bankError: APIError? = nil,
        importStatus: String = "done"
    ) -> OnboardingAPI {
        let mock = MockClient(data: .recorded)
        return OnboardingAPI(
            signInWithApple: { _ in },
            bankAuthLink: { _ in
                if let bankError { throw bankError }
                return ContractExamples.decode("""
                {"url": "https://auth.example.test/?state=abc", "state": "abc", "provider": "monzo", "status": "\(bankStatus)"}
                """)
            },
            bankSummary: { session in try await mock.bankSummary(session: session) },
            importStatement: { _, _, _ in
                var result = OnboardingExamples.importResult
                if importStatus == "failed" {
                    result = ContractExamples.decode("""
                    {"import_id": "imp_2", "status": "failed", "provider": "unknown", "transactions": 0, "months_covered": 0,
                     "warnings": ["No dates found."], "stages": []}
                    """)
                }
                return result
            },
            setManualFinance: { _ in try await mock.financeProfile() },
            reversePostcode: { _, _ in OnboardingExamples.reversePostcode },
            nextMove: { try await mock.nextMove() },
            financeProfile: { try await mock.financeProfile() },
            spending: { month in try await mock.financeSpending(month: month) },
            bills: { try await mock.bills() },
            subscriptions: { try await mock.subscriptions() },
            overview: { try await mock.financeOverview() },
            sources: { try await mock.listSources() },
            habits: { try await mock.habits() }
        )
    }

    private func model(_ api: OnboardingAPI, apple: Bool = false) -> OnboardingViewModel {
        OnboardingViewModel(api: api, appleAvailable: apple, isSampleData: true, stageMinimum: .zero)
    }

    @Test func languageConfirmSwitchesLanguage() {
        let model = model(api())
        var chosen: AppLanguage?
        model.onLanguage = { chosen = $0 }
        model.go(.language)
        model.pickLanguage(.fr)
        #expect(model.state.language == .fr)
        #expect(LanguageScreenTexts.texts(for: model.state.language).confirm == "Confirmer")
        model.confirmLanguage()
        #expect(chosen == .fr)
        #expect(model.state.step == .features)
    }

    @Test func languageScreenFactAndEightLanguages() {
        #expect(AppLanguage.allCases.map(\.nativeName) == ["English", "Français", "Español", "Português", "Italiano", "简体中文", "हिन्दी", "नेपाली"])
        #expect(LanguageScreenTexts.texts(for: .en).studentsFact == "About 1 in 4 students at UK universities come from outside the UK (HESA 2024/25).")
        #expect(LanguageScreenTexts.sourceLine == "HESA, Higher Education Student Statistics 2024/25")
        // Every language has its own title (the screen redraws on tap).
        #expect(Set(AppLanguage.allCases.map { LanguageScreenTexts.texts(for: $0).title }).count == AppLanguage.allCases.count)
        #expect(AppLanguage.comingSoon.contains { $0.code == "ar" } && AppLanguage.comingSoon.contains { $0.code == "ur" })
    }

    @Test func samplesKeepTheServerOrder() {
        let samples: [SampleStatement] = ContractExamples.decode("""
        [{"id": "b", "title": "B", "description": "d", "funding": ["grant"], "months": 3},
         {"id": "a", "title": "A", "description": "d", "funding": ["salary"], "months": 3},
         {"id": "c", "title": "C", "description": "d", "funding": ["family"], "months": 3}]
        """)
        #expect(OnboardingViewModel.sampleCards(samples).map(\.id) == ["b", "a", "c"])
    }

    @Test func appleUnavailableFallsBackToDemo() async {
        let model = model(api(), apple: false)
        model.go(.signIn)
        await model.signInWithApple()
        #expect(model.state.step == .connect)
        #expect(model.state.signIn.note?.contains("demo account") == true)
    }

    @Test func statementImportBuildsTheProfileThenTheMove() async throws {
        let model = model(api())
        await model.importStatement(data: Data("date,amount".utf8), fileName: "monzo.csv")
        #expect(model.state.step == .building)
        #expect(model.state.building.isFinished)
        #expect(model.state.building.stages.first?.detail?.hasPrefix("412 payments") == true)
        let recorded = MockData.recorded.nextMove.top
        #expect(model.state.nextMove?.action == recorded.action)
        #expect(model.state.profile?.noticed.count == min(3, MockData.recorded.financeProfile.personalFacts.count))
        model.next()
        #expect(model.state.step == .profile)
    }

    @Test func failedImportReturnsToConnectWithWarnings() async {
        let model = model(api(importStatus: "failed"))
        model.go(.connect)
        await model.importStatement(data: Data("x".utf8), fileName: "x.csv")
        #expect(model.state.step == .connect)
        #expect(model.state.errorMessage?.contains("No dates found.") == true)
    }

    @Test func statementOver5MBIsRejected() async {
        let model = model(api())
        model.go(.connect)
        await model.importStatement(data: Data(count: OnboardingViewModel.maxStatementBytes + 1), fileName: "big.csv")
        #expect(model.state.step == .connect)
        #expect(model.state.errorMessage?.contains("5 MB") == true)
    }

    @Test func connectOffersSampleStatementAndManualOnly() {
        let model = model(api())
        #expect(model.state.options.map(\.kind) == [.statement, .manual])
    }

    @Test func sampleStudentsShowAndImport() async {
        var api = api()
        let samples: [SampleStatement] = ContractExamples.decode("""
        [{"id": "scholarship", "title": "Scholarship student", "description": "Scholarship and bursary", "funding": ["scholarship", "bursary"], "months": 3}]
        """)
        api.listSamples = { onUpdate in await onUpdate(samples) }
        api.importSample = { _ in OnboardingExamples.importResult }
        let model = model(api)
        await model.connect(.sample)
        #expect(model.state.step == .connect)
        #expect(model.state.samples.map(\.id) == ["scholarship"])
        #expect(model.state.samples.first?.fundingText == "Scholarship · Bursary")
        await model.importSample("scholarship")
        #expect(model.state.step == .building)
        #expect(model.state.building.isFinished)
    }

    @Test func studentFormSendsIncomeSourcesAndMonthlyTotal() {
        let manual = OnboardingFixtures.manualStudent
        #expect(OnboardingViewModel.problems(manual).isEmpty)
        // £1,900 a term x 3 + £380 a month x 12 = £10,260 a year = £855 a month.
        #expect(OnboardingViewModel.monthlyIncome(manual.incomes) == 855)
        let input = OnboardingViewModel.input(manual)
        #expect(input?.isStudent == true)
        #expect(input?.age == 19)
        #expect(input?.monthlyTakeHome == 855)
        #expect(input?.incomeSources?.map(\.kind.rawValue) == ["maintenance_loan", "part_time_job"])
        #expect(input?.studentLoanPlan?.rawValue == "plan_5")
        #expect(input?.debts?.map(\.balance) == [250])
    }

    @Test func studentWithoutIncomeOrAgeIsAsked() {
        var manual = OnboardingFixtures.manualStudent
        manual.incomes = manual.incomes.map { var row = $0; row.isOn = false; return row }
        manual.age = nil
        let problems = OnboardingViewModel.problems(manual)
        #expect(problems.contains("Turn on at least one way money arrives and enter the amount."))
        #expect(problems.contains("Enter your age."))
    }

    @Test func bankCallbackOkReveals() async {
        let model = model(api())
        await model.bankCallback(URL(string: "lifeline://connected?status=ok&session=s1")!)
        #expect(model.state.step == .building)
        #expect(model.state.building.isFinished)
        await model.bankCallback(URL(string: "lifeline://connected?status=error")!)
        #expect(model.state.errorMessage != nil)
    }

    @Test func manualValidationAndInput() async {
        let model = model(api())
        model.go(.manual)
        await model.saveManual()
        #expect(model.state.step == .manual)
        #expect(model.state.manual.problems.contains("Enter a full UK postcode, for example LS6 1AN."))

        var manual = OnboardingFixtures.manualMortgage
        manual.locationNote = nil
        model.updateManual(manual)
        let input = OnboardingViewModel.input(model.state.manual)
        #expect(input?.postcode == "LS6 1AN")
        #expect(input?.mortgageBalance == 180_000)
        #expect(input?.dealEnd == "2027-03-01")
        #expect(input?.monthlyRent == nil)
        await model.saveManual()
        #expect(model.state.step == .building)
        #expect(model.state.building.stages.first?.label == "Saving your numbers")
        #expect(model.state.building.isFinished)
    }

    @Test func dealEndStepperStaysInRange() {
        var manual = OnboardingFixtures.manualMortgage
        manual.dealEndYear = manual.dealEndYears.upperBound
        manual.dealEndMonth = 12
        OnboardingManualView.shiftMonth(&manual, by: 1)
        #expect(manual.dealEndYear == manual.dealEndYears.upperBound && manual.dealEndMonth == 12)
        OnboardingManualView.shiftMonth(&manual, by: -12)
        #expect(manual.dealEndMonth == 12 && manual.dealEndYear == manual.dealEndYears.upperBound - 1)
    }

    @Test func useLocationWithoutHookSaysSo() async {
        let model = model(api())
        await model.useLocation()
        #expect(model.state.manual.locationNote?.contains("not set up") == true)
        model.locate = { (53.82, -1.57) }
        await model.useLocation()
        #expect(model.state.manual.postcode == OnboardingExamples.reversePostcode.postcode)
    }

    // MARK: Account

    @Test func accountLoadResetAndDelete() async {
        var signedOut = false
        let mock = MockClient()
        let expectedName = try? await mock.getMe().displayName
        let api = AccountAPI.from(client: mock)
        let model = AccountViewModel(api: api, isSampleData: true)
        model.onSignedOut = { signedOut = true }
        await model.load()
        #expect(model.state.phase == .ready)
        #expect(model.state.profile?.name == (expectedName.flatMap { $0 } ?? "You"))

        model.actions.onAsk(.reset)
        #expect(model.state.confirm == .reset)
        await model.confirm()
        #expect(model.state.profile?.hasFinanceData == false)
        #expect(model.state.confirm == nil)

        model.actions.onAsk(.delete)
        await model.confirm()
        #expect(signedOut)
    }

    @Test func liveClientWithoutMethodsShowsError() async {
        let api = AccountAPI(
            getMe: { throw OnboardingAPI.notYetAvailable },
            signOut: {}, deleteAccount: {}, resetDemo: { throw OnboardingAPI.notYetAvailable }
        )
        let model = AccountViewModel(api: api, isSampleData: false)
        await model.load()
        if case .failed = model.state.phase {} else { Issue.record("Expected failed phase") }
    }
}
