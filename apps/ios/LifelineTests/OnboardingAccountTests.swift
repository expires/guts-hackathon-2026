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
            financeProfile: { try await mock.financeProfile() }
        )
    }

    private func model(_ api: OnboardingAPI, apple: Bool = false) -> OnboardingViewModel {
        OnboardingViewModel(api: api, appleAvailable: apple, isSampleData: true, stageDelay: .zero)
    }

    @Test func welcomePagesThenSignIn() {
        let model = model(api())
        model.next()
        model.next()
        #expect(model.state.step == .welcome(page: 2))
        model.next()
        #expect(model.state.step == .signIn)
        model.back()
        #expect(model.state.step == .welcome(page: 2))
    }

    @Test func appleUnavailableFallsBackToDemo() async {
        let model = model(api(), apple: false)
        model.go(.signIn)
        await model.signInWithApple()
        #expect(model.state.step == .connect)
        #expect(model.state.signIn.note?.contains("demo account") == true)
    }

    @Test func statementImportAnimatesStagesThenReveals() async throws {
        let model = model(api())
        await model.importStatement(data: Data("date,amount".utf8), fileName: "monzo.csv")
        #expect(model.state.step == .reveal)
        #expect(model.state.importing.shownCount == 5)
        #expect(model.state.importing.summary?.hasPrefix("412 payments") == true)
        let recorded = MockData.recorded.nextMove.top
        #expect(model.state.reveal?.action == recorded.action)
        #expect(model.state.tips.count == min(3, MockData.recorded.financeProfile.personalFacts.count))
        model.next()
        #expect(model.state.step == (model.state.tips.isEmpty ? .reveal : .tips))
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
        #expect(model.state.options.map(\.kind) == [.sample, .statement, .manual])
    }

    @Test func sampleStudentsHideTeamProfilesAndImport() async {
        var api = api()
        let samples: [SampleStatement] = ContractExamples.decode("""
        [{"id": "scholarship", "title": "Scholarship student", "description": "Scholarship and bursary", "funding": ["scholarship", "bursary"], "months": 3, "team": false},
         {"id": "team-ash", "title": "Ash", "description": "Team phone", "funding": ["salary"], "months": 3, "team": true}]
        """)
        api.listSamples = { onUpdate in await onUpdate(samples) }
        api.importSample = { _ in OnboardingExamples.importResult }
        let model = model(api)
        await model.connect(.sample)
        #expect(model.state.step == .samples)
        #expect(model.state.samples.map(\.id) == ["scholarship"])
        #expect(model.state.samples.first?.fundingText == "Scholarship · Bursary")
        await model.importSample("scholarship")
        #expect(model.state.step == .reveal)
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
        #expect(model.state.step == .reveal)
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
        #expect(model.state.step == .reveal)
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
