import Foundation
import Testing
@testable import Lifeline

/// ADR 0069 onboarding: order, Back on every screen, Skip only where it makes sense, build stages tied to
/// real calls, the profile, How Penny decides, and the plain-English confidence fallback.
@MainActor
@Suite("Onboarding redesign (ADR 0069)")
struct OnboardingFlowTests {
    /// Records the calls in order.
    actor Calls {
        private(set) var names: [String] = []
        func add(_ name: String) { names.append(name) }
    }

    /// Holds one call open until the test opens it.
    actor Gate {
        private var continuation: CheckedContinuation<Void, Never>?
        private var isOpen = false
        func wait() async {
            if isOpen { return }
            await withCheckedContinuation { continuation = $0 }
        }
        func open() {
            isOpen = true
            continuation?.resume()
            continuation = nil
        }
    }

    /// Every call answers from the responses recorded for the sample student "scottish".
    private func api(calls: Calls = Calls(), spendingGate: Gate? = nil, failBills: Bool = false) -> OnboardingAPI {
        var api = OnboardingAPI(
            signInWithApple: { _ in },
            bankAuthLink: { _ in throw OnboardingAPI.notYetAvailable },
            bankSummary: { _ in throw OnboardingAPI.notYetAvailable },
            importStatement: { _, _, _ in await calls.add("import"); return OnboardingRecorded.importResult },
            setManualFinance: { _ in await calls.add("manual"); return OnboardingRecorded.profile },
            reversePostcode: { _, _ in OnboardingExamples.reversePostcode },
            forecast: { await calls.add("forecast"); return OnboardingRecorded.forecast },
            financeProfile: { await calls.add("profile"); return OnboardingRecorded.profile }
        )
        api.listSamples = { onUpdate in await onUpdate(OnboardingRecorded.samples.samples) }
        api.importSample = { _ in await calls.add("importSample"); return OnboardingRecorded.importResult }
        api.spending = { month in
            await calls.add(month == nil ? "spending" : "spending \(month!)")
            if let spendingGate { await spendingGate.wait() }
            return OnboardingRecorded.spending(month)
        }
        api.categoryDetail = { category, month in
            await calls.add("paid \(category) \(month ?? "now")")
            if failBills { throw APIError.server(status: 503, code: "down", message: "down", source: "test") }
            return try OnboardingRecorded.categoryDetail(category, month)
        }
        api.bills = {
            await calls.add("bills")
            if failBills { throw APIError.server(status: 503, code: "down", message: "down", source: "test") }
            return OnboardingRecorded.bills
        }
        api.subscriptions = {
            await calls.add("subscriptions")
            if failBills { throw APIError.server(status: 503, code: "down", message: "down", source: "test") }
            return OnboardingRecorded.subscriptions
        }
        api.overview = { await calls.add("overview"); return OnboardingRecorded.overview }
        api.sources = { await calls.add("sources"); return MockData.recorded.sources }
        api.habits = { await calls.add("habits"); return OnboardingRecorded.habits }
        return api
    }

    private func model(_ api: OnboardingAPI) -> OnboardingViewModel {
        OnboardingViewModel(api: api, appleAvailable: false, isSampleData: true, stageMinimum: .zero)
    }

    /// Polls the main actor until `condition` is true (at most about 2 s).
    private func eventually(_ condition: () -> Bool) async -> Bool {
        for _ in 0..<200 {
            if condition() { return true }
            try? await Task.sleep(for: .milliseconds(10))
        }
        return condition()
    }

    // MARK: Order and navigation

    @Test func orderMatchesTheADR() async {
        let model = model(api())
        #expect(model.state.step == .welcome)
        model.next()
        #expect(model.state.step == .problem)
        model.next()
        #expect(model.state.step == .language)
        model.next()
        #expect(model.state.step == .features)
        model.next()
        #expect(model.state.step == .penny)
        model.next()
        #expect(model.state.step == .connect)
        await model.importSample("scottish")
        #expect(model.state.step == .building)
        #expect(model.state.building.isFinished)
        model.next()
        #expect(model.state.step == .profile)
        model.next()
        #expect(model.state.step == .howDecides)
        model.next()
        #expect(model.state.step == .nextMove)
        var finished = false
        model.onFinished = { finished = true }
        model.next()
        #expect(finished)
    }

    @Test func orderConstantHasNoThreeThingsScreen() {
        #expect(OnboardingViewState.order == [.welcome, .problem, .language, .features, .penny, .connect, .building, .profile, .howDecides, .nextMove])
    }

    @Test func backWorksOnEveryScreenAfterWelcome() {
        let model = model(api())
        let order = OnboardingViewState.order
        for index in 1..<order.count {
            model.go(order[index])
            model.back()
            #expect(model.state.step == order[index - 1], "Back from \(order[index])")
        }
        model.go(.manual)
        model.back()
        #expect(model.state.step == .connect)
    }

    @Test func buildingWaitsForViewProfile() async {
        let model = model(api())
        await model.importSample("scottish")
        // No auto-jump: the build ends on its own screen with "View profile".
        #expect(model.state.step == .building)
        #expect(model.state.building.isFinished)
    }

    @Test func skipOnlyWhereItMakesSense() {
        let model = model(api())
        var languageCalls = 0
        model.onLanguage = { _ in languageCalls += 1 }
        let before = AppLanguage.current
        model.go(.language)
        model.pickLanguage(before == .fr ? .es : .fr)
        model.skip()
        #expect(model.state.step == .features)
        #expect(model.state.language == before, "Skip keeps the current language")
        #expect(languageCalls == 0)
        model.go(.penny)
        model.skip()
        #expect(model.state.step == .connect)
        model.go(.howDecides)
        model.skip()
        #expect(model.state.step == .nextMove)
        for step: OnboardingViewState.Step in [.welcome, .problem, .features, .connect, .building, .profile, .nextMove] {
            model.go(step)
            model.skip()
            #expect(model.state.step == step, "No Skip on \(step)")
        }
    }

    @Test func openedFromMoneyBackOnPickYourStudentCloses() {
        var closed = false
        let model = OnboardingViewModel(api: api(), appleAvailable: false, isSampleData: true, startAt: .connect, stageMinimum: .zero)
        model.onFinished = { closed = true }
        #expect(model.state.step == .connect)
        model.back()
        #expect(closed)
    }

    // MARK: Building their profile

    @Test func eightStagesEachEndWhenTheirCallEnds() async {
        let calls = Calls()
        let gate = Gate()
        let model = model(api(calls: calls, spendingGate: gate))
        #expect(OnboardingViewModel.stageIDs.count == 8)
        let build = Task { await model.importSample("scottish") }
        // Spending (stage 3) is held open: stages 1-2 are done, 3 runs, 4-8 wait.
        #expect(await eventually { model.state.building.stages.count == 8 && model.state.building.stages[2].status == .running })
        let statuses = model.state.building.stages.map(\.status)
        #expect(Array(statuses[0...1]) == [.done, .done])
        #expect(statuses[3...].allSatisfy { $0 == .waiting })
        #expect(!model.state.building.isFinished)
        await gate.open()
        await build.value
        #expect(model.state.building.stages.allSatisfy { $0.status == .done })
        #expect(model.state.building.isFinished)
        let names = await calls.names
        #expect(Array(names.prefix(4)) == ["importSample", "profile", "spending", "spending 2026-09"])
        #expect(Set(names[4..<8]) == ["bills", "subscriptions", "paid bills 2026-09", "paid subscriptions 2026-09"])
        #expect(Array(names.suffix(4)) == ["overview", "sources", "habits", "forecast"])
        // Each stage says what its call found.
        #expect(model.state.building.stages[0].detail?.hasPrefix("66 payments") == true)
        #expect(model.state.building.stages[1].detail == "3 income sources")
        #expect(model.state.building.stages[3].detail == "2 bills, 1 subscription")
        #expect(model.state.building.stages[4].detail == "No debts found")
        #expect(model.state.building.stages[6].detail == "Habit score 63 out of 100")
        #expect(model.state.building.stages[7].detail == "Forecast ready")
    }

    @Test func thisMonthSoFarWhenThereIsNoEarlierMonth() async throws {
        var api = api()
        api.spending = { month in
            guard month == nil else { throw APIError.server(status: 404, code: "not_found", message: "none", source: "test") }
            return OnboardingRecorded.spending
        }
        let model = model(api)
        await model.importSample("scottish")
        let profile = try #require(model.state.profile)
        #expect(profile.periodText == "October so far")
        #expect(profile.spendingTotalText?.hasSuffix("in October so far") == true)
    }

    @Test func spendSlicesMergeTheRestAndAddUp() {
        let slices = OnboardingViewModel.spendSlices(OnboardingRecorded.spending)
        #expect(slices.count <= 6)
        #expect(slices.map(\.colorIndex) == Array(0..<slices.count))
        let total = OnboardingRecorded.spending.categories.filter { !["income", "transfers", "savings"].contains($0.category.rawValue) }
            .reduce(0) { $0 + $1.amount }
        #expect(abs(slices.reduce(0) { $0 + $1.amount } - total) < 0.005)
    }

    @Test func habitNamesAreTheOneSet() {
        let names = OnboardingViewModel.habitParts(OnboardingRecorded.habits).map(\.label)
        #expect(names == ["Saving", "Safety cushion", "Steady spending", "Needs before wants", "Subscriptions in check", "Low debt pressure"])
    }

    @Test func failedCallSkipsItsStageAndHidesItsRows() async {
        let model = model(api(failBills: true))
        await model.importSample("scottish")
        #expect(model.state.building.isFinished)
        #expect(model.state.building.stages[3].status == .skipped)
        #expect(model.state.profile?.bills.isEmpty == true)
        #expect(model.state.profile?.spending.isEmpty == false)
    }

    @Test func failedImportGoesBackToPickYourStudent() async {
        var api = api()
        api.importSample = { _ in throw APIError.server(status: 404, code: "not_found", message: "That sample does not exist.", source: "test") }
        let model = model(api)
        await model.importSample("nope")
        #expect(model.state.step == .connect)
        #expect(model.state.errorMessage != nil)
    }

    @Test func backDuringBuildStopsIt() async {
        let gate = Gate()
        let model = model(api(spendingGate: gate))
        let build = Task { await model.importSample("scottish") }
        #expect(await eventually { model.state.building.stages.count == 8 && model.state.building.stages[2].status == .running })
        model.back()
        #expect(model.state.step == .connect)
        await gate.open()
        await build.value
        #expect(model.state.step == .connect, "A stopped build never jumps back")
        #expect(model.state.profile == nil)
    }

    // MARK: Their profile

    @Test func profileShowsEveryPartFromTheCalls() async throws {
        let model = model(api())
        await model.loadSamples()
        await model.importSample("scottish")
        let profile = try #require(model.state.profile)
        #expect(profile.name == "Eilidh Fraser")
        #expect(profile.subtitle == "Age 19 · University of Edinburgh, Edinburgh")
        // Income sources from the profile, with amounts and dates.
        #expect(profile.incomes.map(\.label) == ["Maintenance loan", "Bursary", "Part-time job"])
        #expect(profile.incomes.first?.amountText == "£735 a month")
        #expect(profile.incomes.first?.dates == "18 Sep, 16 Oct · next 16 Nov")
        #expect(profile.housing == "Shared flat in Marchmont, £540 a month")
        #expect(profile.spending.first?.label == "Housing")
        #expect(profile.spending.allSatisfy { !["income", "transfers", "savings"].contains($0.id) })
        // One period for every money block (C7): September, the last full month.
        #expect(profile.periodText == "September")
        #expect(profile.spendingTotalText?.hasSuffix("in September") == true)
        #expect(profile.billsTotalText?.hasSuffix("in September") == true)
        // The bills block is the payments behind the chart's bills and subscriptions slices.
        let chartBills = profile.spending.filter { OnboardingViewModel.billCategories.contains($0.id) }.reduce(0) { $0 + $1.amount }
        let september = OnboardingRecorded.spending("2026-09")
        let paid = OnboardingViewModel.billCategories.compactMap { try? OnboardingRecorded.categoryDetail($0, "2026-09") }
        #expect(abs(paid.reduce(0) { $0 + $1.total } - chartBills) < 0.005)
        #expect(profile.billsTotalText == OnboardingViewModel.amountInPeriod(Money.format(chartBills), month: september.month, currentMonth: "2026-10"))
        #expect(profile.bills.contains { $0.label == "Spotify" && $0.detail?.contains("Subscription") == true })
        // The chart slices add up to the total text, and the shares to about 100%.
        let total = profile.spending.reduce(0) { $0 + $1.amount }
        #expect(profile.spendingTotalText == OnboardingViewModel.spendingTotalText(september, currentMonth: "2026-10"))
        #expect(profile.spendingTotalText?.hasPrefix(Money.format(total)) == true)
        // No "Sample data" tag anywhere (B4).
        #expect(profile.noticed.allSatisfy { $0.sourceText == "From their statement" })
        #expect(profile.noDebts)
        #expect(profile.savingsText == "£300")
        #expect(profile.coverText == "About 1.6 months of spending")
        #expect(profile.habitOverall == 63)
        #expect(profile.habitParts.map(\.value) == [26, 54, 3, 98, 95, 100])
        #expect(profile.noticed.count == 2)
        #expect(profile.noticed.first?.evidence.map(\.valueText) == ["1", "£6"])
        model.toggleNoticed("subscriptions_total")
        #expect(model.state.expandedNoticedID == "subscriptions_total")
        model.toggleNoticed("subscriptions_total")
        #expect(model.state.expandedNoticedID == nil)
    }

    @Test func profileFallsBackWithoutNewFields() {
        var collected = OnboardingFixtures.collected
        collected.profile?.incomeSources = nil
        collected.profile?.monthsOfCover = nil
        collected.profile?.debts = nil
        let profile = OnboardingViewModel.makeProfile(sample: nil, collected: collected)
        // Annual income a month, rent from the decision profile, cover from savings / spending.
        #expect(profile.incomes.map(\.label) == ["Money in"])
        #expect(profile.housing == "Rents, £540 a month")
        #expect(profile.coverText?.hasPrefix("About") == true)
        #expect(profile.name == nil)
    }

    // MARK: Pick your student

    @Test func studentCardShowsTheNewFields() throws {
        let card = try #require(OnboardingViewModel.sampleCards(OnboardingRecorded.samples.samples).first { $0.id == "commuter" })
        #expect(card.title == "Priya Patel")
        #expect(card.kindText == "Commuter student")
        #expect(card.ageText == "19")
        #expect(card.avatar == "face-priya")
        #expect(card.placeText == "University of Manchester, Bolton")
        #expect(card.fundingText == "Access grant + family")
        #expect(card.moneyIn.map(\.amountText) == ["£1,000 a term", "£40 a week"])
        #expect(card.moneyIn.first?.dates == "5 Oct, 1 Feb, 26 Apr")
        #expect(card.housing == "Lives at home with family")
        #expect(card.habitLine?.isEmpty == false)
    }

    @Test func studentCardWithoutNewFieldsHidesRows() throws {
        let card = try #require(OnboardingFixtures.pickStudentOldServer.samples.first)
        #expect(card.title == "Scholarship student")
        #expect(card.kindText == nil && card.ageText == nil && card.placeText == nil && card.housing == nil && card.habitLine == nil)
        #expect(card.moneyIn.isEmpty)
        #expect(card.fundingText == "Scholarship · Bursary")
    }

    // MARK: How Penny decides and Their Next Move

    @Test func howPennyDecidesShowsTheForecastStepsWithSources() throws {
        let forecast = OnboardingRecorded.forecast
        let decides = OnboardingViewModel.makeDecides(forecast)
        #expect(decides.steps.map(\.number) == [1, 2, 3, 4])
        // Money now, bills before the next money, the buffer, the next money: the forecast's own numbers.
        #expect(decides.steps[0].amountText == ForecastText.whole(forecast.moneyAvailable))
        #expect(decides.steps[1].amountText == ForecastText.minusWhole(forecast.billsTotal))
        #expect(decides.steps[2].amountText == ForecastText.minusWhole(forecast.bufferAmount))
        let next = try #require(forecast.nextMoneyIfAny)
        #expect(decides.steps[3].amountText.hasSuffix(ForecastText.whole(next.amount)))
        #expect(decides.steps[0].sources == ["Your statement"])
        #expect(decides.steps[3].sources == [next.source.label])
        #expect(decides.resultText == "= \(ForecastText.whole(forecast.perWeek)) a week")
        #expect(decides.verdict == "On track")
        // No Land Registry, no "Sample data".
        let all = decides.steps.flatMap(\.sources)
        #expect(!all.contains { $0.contains("Land Registry") || $0.contains("Sample data") })
        #expect(OnboardingViewModel.makeDecides(ForecastMock.forecast(ForecastMock.short)).verdict == "Running short")
    }

    @Test func howPennyDecidesAddsExpectedIncomeToMoneyNow() {
        var persona = ForecastMock.onTrack
        persona.expected = [.init(label: "Mum", pence: 4_000, date: "2026-10-23", source: "Your statement, every Friday")]
        let forecast = ForecastMock.forecast(persona)
        let decides = OnboardingViewModel.makeDecides(forecast)
        #expect(decides.steps[0].amountText == ForecastText.whole(forecast.moneyNow + 40))
        #expect(decides.steps[0].detail?.contains("expected before") == true)
        #expect(decides.steps[0].sources.contains("Your statement, every Friday"))
    }

    @Test func theirNextMoveIsTheForecastCard() async throws {
        let model = model(api())
        await model.importSample("scottish")
        let card = try #require(model.state.forecastCard)
        #expect(card == ForecastCardState.make(OnboardingRecorded.forecast))
        // "See the maths" goes back to How Penny decides; "Ask Penny" calls the glue.
        model.go(.nextMove)
        var asked = false
        model.onAskPenny = { asked = true }
        model.actions.onSeeMaths()
        #expect(model.state.step == .howDecides)
        model.actions.onAskPenny()
        #expect(asked)
    }

    @Test func noEmDashesInNewCopy() {
        let rows = OnboardingViewState.featureRows
        #expect(rows.count == 5)
        #expect(rows.map(\.title) == ["See all your money", "Know what you can spend each week", "See the maths behind it", "Ask Penny", "Learn and play with friends"])
        let texts = rows.flatMap { [$0.title, $0.text] } + OnboardingViewModel.stages(firstLabel: "Reading the statement").map(\.label)
        #expect(texts.allSatisfy { !$0.contains("\u{2014}") })
    }
}
