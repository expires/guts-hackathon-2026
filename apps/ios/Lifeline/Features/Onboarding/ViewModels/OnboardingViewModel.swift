import Foundation
import Observation

/// Onboarding flow (ADR 0069, PENNY_V3_BUILD C). Every number on "Their profile", "How Penny decides" and
/// "Their Next Move" comes from a backend call that ends one "Building their profile" stage (sample import,
/// finance profile, spending, bills, accounts, sources, habits, forecast).
@MainActor
@Observable
final class OnboardingViewModel {
    static let maxStatementBytes = 5 * 1024 * 1024

    private let api: OnboardingAPI
    /// Shortest time a build stage stays on screen, for readability (ADR 0069: at most 400 ms). Tests use zero.
    private let stageMinimum: Duration
    private(set) var state: OnboardingViewState

    // Platform hooks, set by the glue.
    /// Runs Sign in with Apple and returns the identity token.
    @ObservationIgnored var appleSignIn: (@MainActor () async throws -> String)?
    /// Opens the bank consent page and returns the callback URL (`lifeline://connected?...`).
    @ObservationIgnored var openBank: (@MainActor (URL) async throws -> URL)?
    /// Shows the file picker. The glue calls `importStatement(data:fileName:)` with the file.
    @ObservationIgnored var pickStatement: @MainActor () -> Void = {}
    /// Current location (latitude, longitude). Nil: location is not set up in this build.
    @ObservationIgnored var locate: (@MainActor () async throws -> (Double, Double))?
    @ObservationIgnored var onFinished: @MainActor () -> Void = {}
    /// The chosen language, after Confirm. The glue switches the app language.
    @ObservationIgnored var onLanguage: @MainActor (AppLanguage) -> Void = { _ in }

    /// Where the flow opened. From `.connect`, Back on "Pick your student" closes onboarding.
    let startAt: OnboardingStep

    /// The sample student being built (nil for an upload or typed numbers).
    @ObservationIgnored private var pickedSample: SampleStatement?
    @ObservationIgnored private var samplesByID: [String: SampleStatement] = [:]
    /// Bumped by Back during a build: a running build stops writing state.
    @ObservationIgnored private var buildGeneration = 0
    /// Raw responses the build collected, for the profile and the next move.
    @ObservationIgnored private var collected = Collected()

    struct Collected {
        var profile: FinanceProfile?
        /// The profile's one period: the last full month, or this month so far when it has no earlier month.
        var spending: SpendingResponse?
        /// This month ("2026-10"), to say "October so far" when `spending` is this month.
        var currentMonth: String?
        var bills: BillsResponse?
        var subscriptions: SubscriptionsResponse?
        /// The bills and subscriptions paid in `spending.month`.
        var billPayments: [CategoryDetail] = []
        var overview: FinanceOverview?
        var sources: [SourceStatus]?
        var habits: HabitScore?
        var forecast: Forecast?
    }

    init(
        api: OnboardingAPI,
        appleAvailable: Bool,
        isSampleData: Bool,
        startAt: OnboardingStep = .welcome,
        now: Date = Date(),
        stageMinimum: Duration = .milliseconds(350)
    ) {
        self.api = api
        self.startAt = startAt
        self.stageMinimum = min(stageMinimum, .milliseconds(400))
        let year = Calendar(identifier: .gregorian).component(.year, from: now)
        let month = Calendar(identifier: .gregorian).component(.month, from: now)
        state = OnboardingViewState(
            signIn: .init(appleAvailable: appleAvailable),
            manual: .init(dealEndYear: year + 1, dealEndMonth: month, dealEndYears: year...(year + 10)),
            isSampleData: isSampleData
        )
        state.language = AppLanguage.current
        if startAt == .connect { go(.connect) }
    }

    var actions: OnboardingActions {
        OnboardingActions(
            onNext: { [weak self] in self?.next() },
            onBack: { [weak self] in self?.back() },
            onSkip: { [weak self] in self?.skip() },
            onSignInWithApple: { [weak self] in Task { await self?.signInWithApple() } },
            onContinueWithoutAccount: { [weak self] in self?.continueWithoutAccount() },
            onConnect: { [weak self] kind in Task { await self?.connect(kind) } },
            onManualChange: { [weak self] manual in self?.updateManual(manual) },
            onAddCost: { [weak self] in self?.addCost() },
            onRemoveCost: { [weak self] id in self?.removeCost(id) },
            onUseLocation: { [weak self] in Task { await self?.useLocation() } },
            onSaveManual: { [weak self] in Task { await self?.saveManual() } },
            onPickLanguage: { [weak self] code in self?.pickLanguage(code) },
            onConfirmLanguage: { [weak self] in self?.confirmLanguage() },
            onPickSample: { [weak self] id in Task { await self?.importSample(id) } },
            onToggleIncome: { [weak self] id in self?.toggleIncome(id) },
            onToggleDebt: { [weak self] id in self?.toggleDebt(id) },
            onToggleNoticed: { [weak self] id in self?.toggleNoticed(id) },
            onFinish: { [weak self] in self?.finish() },
            onSeeMaths: { [weak self] in self?.go(.howDecides) },
            onAskPenny: { [weak self] in self?.askPenny() },
            onDismissError: { [weak self] in self?.state.errorMessage = nil }
        )
    }

    // MARK: Navigation (ADR 0069 order)

    func next() {
        switch state.step {
        case .welcome: go(.problem)
        case .problem: go(.language)
        case .language: confirmLanguage()
        case .features: go(.penny)
        case .penny, .signIn: go(.connect)
        case .building: if state.building.isFinished { go(.profile) }
        case .profile: go(.howDecides)
        case .howDecides: go(.nextMove)
        case .nextMove: finish()
        case .connect, .manual: break
        }
    }

    func back() {
        switch state.step {
        case .welcome: break
        case .problem: go(.welcome)
        case .language: go(.problem)
        case .features: go(.language)
        case .penny: go(.features)
        case .signIn: go(.penny)
        case .connect: if startAt == .connect { finish() } else { go(.penny) }
        case .manual: go(.connect)
        case .building:
            // Stop the running build; its late results are dropped.
            buildGeneration += 1
            go(.connect)
        case .profile: go(.building)
        case .howDecides: go(.profile)
        case .nextMove: go(.howDecides)
        }
    }

    /// Skip where it makes sense (ADR 0069): Language keeps the current language, Try Penny, How Penny decides.
    func skip() {
        switch state.step {
        case .language:
            state.language = AppLanguage.current
            go(.features)
        case .penny: go(.connect)
        case .howDecides: go(.nextMove)
        default: break
        }
    }

    /// Live preview: the language screen redraws in this language at once.
    func pickLanguage(_ language: AppLanguage) {
        state.language = language
    }

    func confirmLanguage() {
        onLanguage(state.language)
        // The screens built by the ViewModel follow the new language.
        if state.profile != nil || state.forecastCard != nil { rebuildFromCollected() }
        go(.features)
    }

    func go(_ step: OnboardingViewState.Step) {
        state.errorMessage = nil
        state.step = step
        // "Pick your student" shows the sample students first.
        if step == .connect, state.samples.isEmpty, !state.samplesLoading {
            Task { await loadSamples() }
        }
    }

    func finish() {
        onFinished()
    }

    /// Opens Penny with the forecast loaded. Set by the glue.
    @ObservationIgnored var onAskPenny: @MainActor () -> Void = {}

    func askPenny() {
        onAskPenny()
    }

    func toggleNoticed(_ id: String) {
        state.expandedNoticedID = state.expandedNoticedID == id ? nil : id
    }

    // MARK: Sign in

    func signInWithApple() async {
        guard state.signIn.appleAvailable, let appleSignIn else {
            continueWithoutAccount(note: L10n.tr("Sign in with Apple is not set up in this build. You use a demo account on this phone."))
            return
        }
        state.isBusy = true
        defer { state.isBusy = false }
        do {
            let token = try await appleSignIn()
            try await api.signInWithApple(token)
            state.signIn.note = nil
            go(.connect)
        } catch {
            continueWithoutAccount(note: L10n.tr("Sign in with Apple did not work. You use a demo account on this phone."))
        }
    }

    /// Demo sign-in: the client signs in with the device id on the first request.
    func continueWithoutAccount(note: String? = nil) {
        state.signIn.note = note
        go(.connect)
        state.errorMessage = nil
    }

    // MARK: Pick your student

    func connect(_ kind: OnboardingViewState.ConnectOption.Kind) async {
        state.errorMessage = nil
        switch kind {
        case .sample:
            go(.connect)
            await loadSamples()
        case .monzo: await connectMonzo()
        case .trading212:
            if api.hasTrading212 { break }
            markUnavailable(.trading212)
            state.errorMessage = L10n.tr("Trading 212 is not available yet. Upload a statement or enter your numbers.")
        case .statement: pickStatement()
        case .manual: go(.manual)
        }
    }

    private func markUnavailable(_ kind: OnboardingViewState.ConnectOption.Kind) {
        if let index = state.options.firstIndex(where: { $0.kind == kind }) {
            state.options[index].isUnavailable = true
        }
    }

    private func connectMonzo() async {
        state.isBusy = true
        defer { state.isBusy = false }
        do {
            let link = try await api.bankAuthLink("monzo")
            guard link.status != .unavailable, let url = URL(string: link.url) else {
                return monzoUnavailable()
            }
            guard let openBank else { return monzoUnavailable() }
            let callback = try await openBank(url)
            await bankCallback(callback)
        } catch let error as APIError {
            if case let .server(status, _, _, _) = error, status == 409 || status == 501 || status == 503 {
                monzoUnavailable()
            } else {
                state.errorMessage = error.userMessage
            }
        } catch {
            // The user closed the consent page.
            state.errorMessage = L10n.tr("Monzo was not connected. Try again, or use another way.")
        }
    }

    private func monzoUnavailable() {
        markUnavailable(.monzo)
        state.errorMessage = L10n.tr("Monzo is unavailable right now. Upload a statement or enter your numbers.")
    }

    /// `lifeline://connected?status=ok|error&session=...`
    func bankCallback(_ url: URL) async {
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        let status = items.first { $0.name == "status" }?.value
        guard status == "ok", let session = items.first(where: { $0.name == "session" })?.value else {
            state.errorMessage = L10n.tr("Monzo was not connected. Try again, or use another way.")
            return
        }
        pickedSample = nil
        await build(firstLabel: L10n.tr("Reading the statement")) { [api] in
            _ = try await api.bankSummary(session)
            return nil
        }
    }

    /// The student cards, exactly as the server lists them, in its order. Cached first (ADR 0060).
    func loadSamples() async {
        if state.samples.isEmpty { state.samplesLoading = true }
        defer { state.samplesLoading = false }
        do {
            try await api.listSamples { [weak self] samples in
                guard let self else { return }
                samplesByID = Dictionary(samples.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
                state.samples = Self.sampleCards(samples)
                state.samplesLoading = false
            }
        } catch {
            if state.samples.isEmpty { state.errorMessage = APIError.map(error).userMessage }
        }
    }

    static func sampleCards(_ samples: [SampleStatement]) -> [OnboardingViewState.SampleCard] {
        samples.map(sampleCard)
    }

    /// One card. Every new ADR 0069 field is optional: a missing field hides its row.
    static func sampleCard(_ sample: SampleStatement) -> OnboardingViewState.SampleCard {
        let name = sample.name.flatMap(nonEmpty)
        let place = [sample.uni, sample.city].compactMap { $0.flatMap(nonEmpty) }.joined(separator: ", ")
        return .init(
            id: sample.id,
            title: name ?? sample.title,
            kindText: name == nil ? nil : sample.title,
            ageText: sample.age.map { String($0) },
            avatar: sample.avatar.flatMap(nonEmpty),
            placeText: place.isEmpty ? nil : place,
            fundingText: sample.fundingLabel.flatMap(nonEmpty)
                ?? sample.funding.map { fundingLabel($0.rawValue) }.joined(separator: " · "),
            moneyIn: (sample.moneyIn ?? []).enumerated().map { offset, line in moneyInLine(line, index: offset) },
            housing: sample.housing.flatMap(nonEmpty),
            habitLine: sample.habitLine.flatMap(nonEmpty),
            text: sample.description
        )
    }

    /// "£280 a month", "£1,000 a term", "£40 a week", "£3,612 a year".
    static func moneyInLine(_ line: Components.Schemas.SampleMoneyIn, index: Int) -> OnboardingViewState.MoneyInLine {
        let amount = Money.format(line.amount)
        let text = switch line.period {
        case .week: L10n.tr("\(amount) a week")
        case .month: L10n.tr("\(amount) a month")
        case .term: L10n.tr("\(amount) a term")
        case .year: L10n.tr("\(amount) a year")
        }
        return .init(id: "\(index).\(line.label)", label: line.label, amountText: text, dates: line.dates.flatMap(nonEmpty))
    }

    /// "Maintenance loan", in the app language.
    static func fundingLabel(_ raw: String) -> String {
        switch raw {
        case "maintenance_loan": L10n.tr("Maintenance loan")
        case "scholarship": L10n.tr("Scholarship")
        case "bursary": L10n.tr("Bursary")
        case "grant": L10n.tr("Grant")
        case "family": L10n.tr("Parents or family")
        case "part_time_job": L10n.tr("Part-time job")
        case "salary": L10n.tr("Salary")
        case "other": L10n.tr("Other")
        default: raw.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    private static func nonEmpty(_ text: String) -> String? {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    /// Imports the sample student's statement through the real pipeline, then builds the profile.
    func importSample(_ id: String) async {
        pickedSample = samplesByID[id]
        await build(firstLabel: L10n.tr("Reading the statement")) { [api] in
            let result = try await api.importSample(id)
            return result
        }
    }

    // MARK: Statement

    func importStatement(data: Data, fileName: String) async {
        guard data.count <= Self.maxStatementBytes else {
            state.errorMessage = L10n.tr("This file is larger than 5 MB. Export a shorter period and try again.")
            return
        }
        let provider: String? = fileName.lowercased().hasSuffix(".pdf") ? "pdf" : nil
        pickedSample = nil
        await build(firstLabel: L10n.tr("Reading the statement")) { [api] in
            try await api.importStatement(data, fileName, provider)
        }
    }

    /// "412 payments, 1 Apr 2026 to 16 Oct 2026".
    static func importSummary(_ result: Components.Schemas.ImportResult) -> String {
        let count = result.transactions == 1 ? L10n.tr("1 payment") : L10n.tr("\(result.transactions) payments")
        guard let first = result.firstDate.flatMap(FinanceMapping.date), let last = result.lastDate.flatMap(FinanceMapping.date) else {
            return count
        }
        let format = Date.FormatStyle(date: .abbreviated, time: .omitted).locale(FinanceMapping.dateLocale)
        return L10n.tr("\(count), \(first.formatted(format)) to \(last.formatted(format))")
    }

    // MARK: Manual entry

    func updateManual(_ manual: OnboardingViewState.Manual) {
        state.manual = manual
        if !state.manual.problems.isEmpty { state.manual.problems = Self.problems(manual) }
    }

    func addCost() {
        guard state.manual.costs.count < 30 else { return }
        let id = (state.manual.costs.map(\.id).max() ?? 0) + 1
        state.manual.costs.append(.init(id: id, name: "", monthlyAmount: 0))
    }

    func removeCost(_ id: Int) {
        state.manual.costs.removeAll { $0.id == id }
    }

    func useLocation() async {
        guard let locate else {
            state.manual.locationNote = L10n.tr("Location is not set up yet. Type your postcode.")
            return
        }
        state.manual.isLocating = true
        defer { state.manual.isLocating = false }
        do {
            let (lat, lon) = try await locate()
            let found = try await api.reversePostcode(lat, lon)
            state.manual.postcode = found.postcode
            state.manual.locationNote = "\(found.town), from your location"
        } catch {
            state.manual.locationNote = L10n.tr("We could not find your postcode. Type it instead.")
        }
    }

    static func problems(_ manual: OnboardingViewState.Manual) -> [String] {
        var problems: [String] = []
        let postcode = manual.postcode.trimmingCharacters(in: .whitespaces)
        let allowed = CharacterSet.alphanumerics.union(.init(charactersIn: " "))
        if postcode.count < 5 || postcode.count > 8 || postcode.unicodeScalars.contains(where: { !allowed.contains($0) }) {
            problems.append(L10n.tr("Enter a full UK postcode, for example LS6 1AN."))
        }
        if manual.isStudent {
            if !manual.incomes.contains(where: { $0.isOn && $0.amount > 0 }) {
                problems.append(L10n.tr("Turn on at least one way money arrives and enter the amount."))
            }
        } else if manual.monthlyTakeHome <= 0 || manual.monthlyTakeHome > 1_000_000 {
            problems.append(L10n.tr("Enter your take-home pay a month."))
        }
        if let age = manual.age, !(16...100).contains(age) {
            problems.append(L10n.tr("Enter an age from 16 to 100."))
        } else if manual.age == nil {
            problems.append(L10n.tr("Enter your age."))
        }
        switch manual.housing {
        case .rent:
            if manual.monthlyRent <= 0 || manual.monthlyRent > 100_000 { problems.append(L10n.tr("Enter your rent a month.")) }
        case .mortgage:
            if manual.mortgageBalance <= 0 { problems.append(L10n.tr("Enter what you still owe on the mortgage.")) }
            if manual.mortgageRatePercent <= 0 || manual.mortgageRatePercent > 30 { problems.append(L10n.tr("Enter your mortgage rate, for example 4.4.")) }
        case .own, .parents:
            break
        }
        if manual.costs.contains(where: { $0.name.trimmingCharacters(in: .whitespaces).isEmpty || $0.monthlyAmount < 0 }) {
            problems.append(L10n.tr("Give every regular cost a name."))
        }
        return problems
    }

    /// A student's money a month from their own sources: weekly x 52, monthly x 12, termly x 3, yearly x 1, then / 12.
    static func monthlyIncome(_ incomes: [OnboardingViewState.IncomeRow]) -> Double {
        let yearly = incomes.filter { $0.isOn && $0.amount > 0 }.reduce(0) { $0 + $1.amount * $1.schedule.perYear }
        return (yearly / 12 * 100).rounded() / 100
    }

    func toggleIncome(_ id: String) {
        guard let index = state.manual.incomes.firstIndex(where: { $0.id == id }) else { return }
        state.manual.incomes[index].isOn.toggle()
    }

    func toggleDebt(_ id: String) {
        guard let index = state.manual.debts.firstIndex(where: { $0.id == id }) else { return }
        state.manual.debts[index].isOn.toggle()
    }

    /// The request body for `PUT /v1/finance/manual`. Only the fields that apply to the housing choice.
    /// Students send their income sources; `monthly_take_home` is then their monthly total from those sources.
    static func input(_ manual: OnboardingViewState.Manual) -> Components.Schemas.ManualFinanceInput? {
        let incomes = manual.incomes.filter { $0.isOn && $0.amount > 0 }
        var body: [String: Any] = [
            "postcode": manual.postcode.trimmingCharacters(in: .whitespaces).uppercased(),
            "housing": manual.housing.rawValue,
            "monthly_take_home": manual.isStudent ? monthlyIncome(manual.incomes) : manual.monthlyTakeHome,
            "is_student": manual.isStudent,
            "income_sources": incomes.map { ["id": $0.id, "kind": $0.kind.rawValue, "amount": $0.amount, "schedule": $0.schedule.rawValue] },
            "debts": manual.debts.filter { $0.isOn && $0.balance > 0 }.map { ["id": $0.id, "kind": $0.kind.rawValue, "balance": $0.balance] },
            "savings": manual.savings,
            "regular_costs": manual.costs.map { ["name": $0.name.trimmingCharacters(in: .whitespaces), "monthly_amount": $0.monthlyAmount] },
        ]
        if let age = manual.age { body["age"] = age }
        if let plan = manual.loanPlan { body["student_loan_plan"] = plan.rawValue }
        switch manual.housing {
        case .rent:
            body["monthly_rent"] = manual.monthlyRent
        case .mortgage:
            body["mortgage_balance"] = manual.mortgageBalance
            body["mortgage_rate_pct"] = manual.mortgageRatePercent
            body["deal_end"] = String(format: "%04d-%02d-01", manual.dealEndYear, manual.dealEndMonth)
        case .own, .parents:
            break
        }
        guard let data = try? JSONSerialization.data(withJSONObject: body) else { return nil }
        return try? JSONDecoder().decode(Components.Schemas.ManualFinanceInput.self, from: data)
    }


    func saveManual() async {
        let problems = Self.problems(state.manual)
        state.manual.problems = problems
        guard problems.isEmpty, let input = Self.input(state.manual) else { return }
        pickedSample = nil
        await build(firstLabel: L10n.tr("Saving your numbers")) { [api] in
            _ = try await api.setManualFinance(input)
            return nil
        }
    }

    // MARK: Building their profile (ADR 0069)

    /// Stage ids in order. Each stage ends when its call ends.
    static let stageIDs = ["read", "income", "spending", "bills", "debts", "live_data", "habits", "profile"]

    static func stages(firstLabel: String) -> [OnboardingViewState.BuildStage] {
        let labels = [
            firstLabel,
            L10n.tr("Finding income sources"),
            L10n.tr("Sorting spending"),
            L10n.tr("Finding bills and subscriptions"),
            L10n.tr("Checking debts"),
            L10n.tr("Checking live UK data"),
            L10n.tr("Scoring habits"),
            L10n.tr("Building the profile"),
        ]
        return zip(stageIDs, labels).map { .init(id: $0, label: $1) }
    }

    private func isCurrent(_ generation: Int) -> Bool {
        generation == buildGeneration && state.step == .building
    }

    /// Runs one stage: marks it running, waits for its call, keeps it on screen for at least `stageMinimum`.
    /// Nil when Back stopped the build meanwhile.
    private func run<T: Sendable>(
        _ index: Int, _ generation: Int, _ work: @Sendable () async throws -> T
    ) async -> Result<T, any Error>? {
        guard isCurrent(generation) else { return nil }
        state.building.stages[index].status = .running
        let clock = ContinuousClock()
        let start = clock.now
        let result: Result<T, any Error>
        do { result = .success(try await work()) } catch { result = .failure(error) }
        let elapsed = clock.now - start
        if elapsed < stageMinimum { try? await Task.sleep(for: stageMinimum - elapsed) }
        guard isCurrent(generation) else { return nil }
        return result
    }

    private func end(_ index: Int, detail: String?) {
        state.building.stages[index].status = .done
        state.building.stages[index].detail = detail
    }

    /// A failed non-critical call: the stage shows as skipped and its profile rows stay hidden.
    private func skipStage(_ index: Int) {
        state.building.stages[index].status = .skipped
        state.building.stages[index].detail = L10n.tr("Not available right now")
    }

    /// The 8 stages in order. Stage 1 (`read`) and stage 8 (the next move) must work; the others may be skipped.
    func build(
        firstLabel: String,
        read: @escaping @Sendable () async throws -> Components.Schemas.ImportResult?
    ) async {
        buildGeneration += 1
        let generation = buildGeneration
        collected = Collected()
        state.profile = nil
        state.decides = nil
        state.forecastCard = nil
        state.expandedNoticedID = nil
        state.building = .init(stages: Self.stages(firstLabel: firstLabel))
        go(.building)

        // 1. Reading the statement (or saving the typed numbers).
        guard let readResult = await run(0, generation, read) else { return }
        switch readResult {
        case let .success(result):
            if let result {
                guard result.status != .failed else {
                    go(.connect)
                    state.errorMessage = ([L10n.tr("We could not read this statement.")] + (result.warnings ?? [])).joined(separator: " ")
                    return
                }
                end(0, detail: Self.importSummary(result))
            } else {
                end(0, detail: nil)
            }
        case let .failure(error):
            return failImport(error)
        }

        // 2. Finding income sources: the finance profile.
        guard let profile = await run(1, generation, { [api] in try await api.financeProfile() }) else { return }
        if case let .success(value) = profile {
            collected.profile = value
            end(1, detail: Self.incomeDetail(sample: pickedSample, profile: value))
        } else { skipStage(1) }

        // 3. Sorting spending: the last full month, so the chart, bills and subscriptions cover the same whole
        // month (C7). This month so far only when there is no earlier month.
        guard let spending = await run(2, generation, { [api] in
            let now = try await api.spending(nil)
            guard let previous = Self.previousMonth(now.month), let earlier = try? await api.spending(previous),
                  !Self.spendSlices(earlier).isEmpty else { return (now, now.month) }
            return (earlier, now.month)
        }) else { return }
        if case let .success(pair) = spending {
            collected.spending = pair.0
            collected.currentMonth = pair.1
            end(2, detail: Self.spendingTotalText(pair.0, currentMonth: pair.1))
        } else { skipStage(2) }

        // 4. Finding bills and subscriptions.
        // The payments come from the same month as the chart, for the categories the chart has.
        let paidMonth = collected.spending?.month
        let paidCategories = Self.billCategories.filter { id in
            collected.spending?.categories.contains { $0.category.rawValue == id && $0.amount > 0 } == true
        }
        guard let bills = await run(3, generation, { [api] in
            async let bills = try? api.bills()
            async let subscriptions = try? api.subscriptions()
            var payments: [CategoryDetail] = []
            for category in paidCategories {
                if let detail = try? await api.categoryDetail(category, paidMonth) { payments.append(detail) }
            }
            let pair = await (bills, subscriptions)
            if pair.0 == nil && pair.1 == nil && payments.isEmpty { throw OnboardingAPI.notYetAvailable }
            return (pair.0, pair.1, payments)
        }) else { return }
        if case let .success(pair) = bills {
            collected.bills = pair.0
            collected.subscriptions = pair.1
            collected.billPayments = pair.2
            end(3, detail: Self.billsDetail(bills: pair.0, subscriptions: pair.1))
        } else { skipStage(3) }

        // 5. Checking debts: the accounts.
        guard let overview = await run(4, generation, { [api] in try await api.overview() }) else { return }
        if case let .success(value) = overview {
            collected.overview = value
            let count = Self.debtRows(overview: value, profile: collected.profile).count
            end(4, detail: count == 0 ? L10n.tr("No debts found") : (count == 1 ? L10n.tr("1 debt") : L10n.tr("\(count) debts")))
        } else { skipStage(4) }

        // 6. Checking live UK data: the sources status.
        guard let sources = await run(5, generation, { [api] in try await api.sources() }) else { return }
        if case let .success(value) = sources {
            collected.sources = value
            let live = value.filter { $0.status == .live }.count
            end(5, detail: L10n.tr("\(live) of \(value.count) sources live"))
        } else { skipStage(5) }

        // 7. Scoring habits.
        guard let habits = await run(6, generation, { [api] in try await api.habits() }) else { return }
        if case let .success(value) = habits {
            collected.habits = value
            end(6, detail: value.overall.map { L10n.tr("Habit score \($0) out of 100") })
        } else { skipStage(6) }

        // 8. Building the profile: the forecast (ADR 0072).
        guard let forecast = await run(7, generation, { [api] in try await api.forecast() }) else { return }
        switch forecast {
        case let .success(value):
            collected.forecast = value
            end(7, detail: L10n.tr("Forecast ready"))
        case let .failure(error):
            return failImport(error)
        }
        rebuildFromCollected()
        state.building.isFinished = true
    }

    /// Profile, "How Penny decides" and "Their Next Move" from the collected responses.
    private func rebuildFromCollected() {
        state.profile = Self.makeProfile(sample: pickedSample, collected: collected)
        if let forecast = collected.forecast {
            state.decides = Self.makeDecides(forecast)
            state.forecastCard = ForecastCardState.make(forecast)
        }
    }

    private func failImport(_ error: Error) {
        let mapped = APIError.map(error)
        go(.connect)
        state.errorMessage = mapped.isNoFinanceData
            ? L10n.tr("We could not build a profile from this. Try another way.")
            : mapped.userMessage
    }

    // MARK: Mapping (pure, used by fixtures and tests)

    static func incomeDetail(sample: SampleStatement?, profile: FinanceProfile) -> String {
        let fromProfile = profile.incomeSources?.count ?? 0
        let count = fromProfile > 0 ? fromProfile : (sample?.moneyIn?.count ?? (profile.profile.annualIncome > 0 ? 1 : 0))
        return count == 1 ? L10n.tr("1 income source") : L10n.tr("\(count) income sources")
    }

    /// The categories whose payments make the "Bills and subscriptions" block.
    nonisolated static let billCategories = ["bills", "subscriptions"]

    /// Categories that are spending (not income, transfers or savings), largest first. The 6th and smaller merge
    /// into one "Everything else" slice, so the slices always add up to the shown total.
    nonisolated static func spendSlices(_ response: SpendingResponse) -> [OnboardingViewState.SpendSlice] {
        let skip: Set<String> = ["income", "transfers", "savings"]
        let all = response.categories
            .filter { !skip.contains($0.category.rawValue) && $0.amount > 0 }
            .sorted { $0.amount > $1.amount }
        var parts: [(id: String, label: String, amount: Double)] = all.prefix(5).map { ($0.category.rawValue, $0.label, $0.amount) }
        let rest = all.dropFirst(5)
        if rest.count == 1, let only = rest.first {
            parts.append((only.category.rawValue, only.label, only.amount))
        } else if !rest.isEmpty {
            parts.append(("rest", L10n.tr("Everything else"), rest.reduce(0) { $0 + $1.amount }))
        }
        let total = parts.reduce(0) { $0 + $1.amount }
        return parts.enumerated().map { index, part in
            let share = total > 0 ? part.amount / total : 0
            return .init(
                id: part.id, label: part.label, amount: part.amount, amountText: Money.format(part.amount),
                shareText: Int((share * 100).rounded()).description + "%", colorIndex: index
            )
        }
    }

    /// "2026-10" -> "2026-09".
    nonisolated static func previousMonth(_ month: String) -> String? {
        let parts = month.split(separator: "-").compactMap { Int($0) }
        guard parts.count >= 2 else { return nil }
        let (year, value) = parts[1] == 1 ? (parts[0] - 1, 12) : (parts[0], parts[1] - 1)
        return String(format: "%04d-%02d", year, value)
    }

    /// "£1,796 in September" or "£512 in October so far".
    static func spendingTotalText(_ response: SpendingResponse, currentMonth: String?) -> String {
        let total = spendSlices(response).reduce(0) { $0 + $1.amount }
        return amountInPeriod(Money.format(total), month: response.month, currentMonth: currentMonth)
    }

    /// "£14 in September" or "£14 in October so far".
    static func amountInPeriod(_ amount: String, month: String, currentMonth: String?) -> String {
        let name = monthName(month)
        return month == currentMonth ? L10n.tr("\(amount) in \(name) so far") : L10n.tr("\(amount) in \(name)")
    }

    /// "September" or "October so far": the profile's one period.
    static func periodText(month: String, currentMonth: String?) -> String {
        let name = monthName(month)
        let text = month == currentMonth ? L10n.tr("\(name) so far") : name
        return text.prefix(1).uppercased() + text.dropFirst()
    }

    /// "September", in the app language.
    static func monthName(_ month: String) -> String {
        guard let date = FinanceMapping.date(month + "-01") else { return month }
        var format = Date.FormatStyle().locale(FinanceMapping.dateLocale).month(.wide)
        format.timeZone = TimeZone(identifier: "UTC") ?? .gmt
        return date.formatted(format)
    }

    static func billsDetail(bills: BillsResponse?, subscriptions: SubscriptionsResponse?) -> String {
        let billCount = (bills?.items ?? []).filter { $0.kind != .subscription }.count
        let subCount = subscriptions?.count ?? 0
        let billText = billCount == 1 ? L10n.tr("1 bill") : L10n.tr("\(billCount) bills")
        let subText = subCount == 1 ? L10n.tr("1 subscription") : L10n.tr("\(subCount) subscriptions")
        return L10n.tr("\(billText), \(subText)")
    }

    /// Money owed. The profile's `debts` first; without them, credit and loan accounts below zero, an overdrawn
    /// current account, or the profile's other debt.
    static func debtRows(overview: FinanceOverview?, profile: FinanceProfile?) -> [OnboardingViewState.ProfileRow] {
        if let debts = profile?.debts, !debts.isEmpty {
            return debts.map { debt in
                let label = switch debt.kind {
                case .card: L10n.tr("Credit card")
                case .overdraft: L10n.tr("Overdraft")
                case .bnpl: L10n.tr("Buy now, pay later")
                case .loan: L10n.tr("Loan")
                }
                var details: [String] = []
                if let rate = debt.ratePct {
                    let percent = rate.formatted(.number.precision(.fractionLength(0...2)).locale(Money.locale)) + "%"
                    details.append(L10n.tr("\(percent) a year"))
                }
                if let due = debt.dueDate { details.append(L10n.tr("Due \(FinanceMapping.dayText(due))")) }
                return .init(
                    id: debt.id, label: label, valueText: Money.format(debt.balance),
                    detail: details.isEmpty ? nil : details.joined(separator: " · ")
                )
            }
        }
        var rows: [OnboardingViewState.ProfileRow] = (overview?.accounts ?? []).compactMap { account in
            guard account.balance < 0 else { return nil }
            switch account.kind {
            case .credit, .loan:
                return .init(id: account.id, label: account.name, valueText: Money.format(-account.balance))
            case .current:
                return .init(id: account.id, label: L10n.tr("Overdraft"), valueText: Money.format(-account.balance), detail: account.name)
            default:
                return nil
            }
        }
        if rows.isEmpty, let other = profile?.profile.otherDebt, other > 0 {
            rows.append(.init(id: "other_debt", label: L10n.tr("Debt"), valueText: Money.format(other)))
        }
        return rows
    }

    static func housingText(_ profile: DecisionProfile, rent foundRent: Double? = nil) -> String {
        switch profile.housing {
        case .rent:
            if let rent = foundRent ?? profile.monthlyRent, rent > 0 { return L10n.tr("Rents, \(Money.format(rent)) a month") }
            return L10n.tr("Rents")
        case .parents: return L10n.tr("Lives with family")
        case .own: return L10n.tr("Owns their home")
        case .mortgage:
            if let balance = profile.mortgageBalance, balance > 0 { return L10n.tr("Mortgage, \(Money.format(balance)) left") }
            return L10n.tr("Mortgage")
        }
    }

    /// The 6 habit parts as 0-100 bars, no amounts (ADR 0052).
    static func habitParts(_ score: HabitScore) -> [OnboardingViewState.HabitPart] {
        let parts = score.components
        let rows: [(String, String, Int?)] = [
            ("savings_rate", L10n.tr("Saving"), parts.savingsRate),
            ("months_of_cover", L10n.tr("Safety cushion"), parts.monthsOfCover),
            ("spend_stability", L10n.tr("Steady spending"), parts.spendStability),
            ("discretionary_share", L10n.tr("Needs before wants"), parts.discretionaryShare),
            ("subscription_creep", L10n.tr("Subscriptions in check"), parts.subscriptionCreep),
            ("debt_pressure", L10n.tr("Low debt pressure"), parts.debtPressure),
        ]
        return rows.compactMap { id, label, value in
            value.map { .init(id: id, label: label, value: min(100, max(0, $0))) }
        }
    }

    /// One income source from the profile: "Maintenance loan", "£1,638 a term", "28 Sep, 18 Jan · next 18 Jan".
    static func incomeLine(_ source: Components.Schemas.IncomeSource) -> OnboardingViewState.MoneyInLine {
        let amount = Money.format(source.amount)
        let amountText = switch source.schedule {
        case .weekly: L10n.tr("\(amount) a week")
        case .fortnightly: L10n.tr("\(amount) every 2 weeks")
        case .monthly: L10n.tr("\(amount) a month")
        case .termly: L10n.tr("\(amount) a term")
        case .yearly: L10n.tr("\(amount) a year")
        case .oneOff: L10n.tr("\(amount) once")
        }
        // Paid dates up to the next one (ISO dates sort as text), then the next date.
        let paid = (source.dates ?? []).filter { date in source.nextDate.map { date < $0 } ?? true }
        let dates = paid.suffix(source.nextDate == nil ? 3 : 2).map(shortDay).joined(separator: ", ")
        let next = source.nextDate.map { L10n.tr("next \(shortDay($0))") }
        let line = [dates.isEmpty ? nil : dates, next].compactMap { $0 }.joined(separator: " · ")
        return .init(id: source.id, label: fundingLabel(source.kind.rawValue), amountText: amountText, dates: line.isEmpty ? nil : line)
    }

    /// "18 Sep".
    static func shortDay(_ raw: String) -> String {
        FinanceMapping.date(raw).map { FinanceMapping.format($0, template: "dMMM") } ?? raw
    }

    /// Icon id for a personal fact's concept.
    static func noticedIcon(_ conceptID: String) -> String {
        switch conceptID {
        case "budgeting": LLIcon.subscriptions.rawValue
        case "emergency-fund": LLIcon.savings.rawValue
        case "interest-rates": LLIcon.rateRise.rawValue
        case "compound-interest": LLIcon.investment.rawValue
        case "debt", "credit", "overdraft", "bnpl": LLIcon.debt.rawValue
        case "student-finance", "student-loans": LLIcon.study.rawValue
        default: LLIcon.why.rawValue
        }
    }

    /// The fact's numbers as evidence rows: "Monthly total: £38".
    static func evidenceRows(_ fact: PersonalFact) -> [OnboardingViewState.ProfileRow] {
        let moneyWords = ["total", "amount", "spend", "savings", "interest", "liquid", "balance", "income", "cost", "rent"]
        return fact.facts.additionalProperties.keys.sorted().compactMap { key in
            guard let value = fact.facts.additionalProperties[key] else { return nil }
            let label = key.replacingOccurrences(of: "_", with: " ").capitalized(with: Locale(identifier: "en_GB"))
            let text: String
            if key.hasSuffix("pct") || key.hasSuffix("percent") {
                text = value.formatted(.number.precision(.fractionLength(0...2)).locale(Money.locale)) + "%"
            } else if moneyWords.contains(where: { key.contains($0) }) {
                text = Money.format(value)
            } else {
                text = value.formatted(.number.precision(.fractionLength(0...1)).locale(Money.locale))
            }
            return .init(id: key, label: label, valueText: text)
        }
    }

    static func makeProfile(sample: SampleStatement?, collected: Collected) -> OnboardingViewState.Profile {
        var profile = OnboardingViewState.Profile()
        let decision = collected.profile?.profile
        if let sample {
            let card = sampleCard(sample)
            profile.name = card.title
            profile.subtitle = [card.ageText.map { L10n.tr("Age \($0)") }, card.placeText].compactMap { $0 }.joined(separator: " · ")
            profile.avatar = card.avatar
            profile.incomes = card.moneyIn
            profile.housing = card.housing
        }
        // Income sources found in the statement (or typed) win: amounts per payment and dates.
        if let sources = collected.profile?.incomeSources, !sources.isEmpty {
            profile.incomes = sources.map(incomeLine)
        }
        if profile.incomes.isEmpty, let decision, decision.annualIncome > 0 {
            profile.incomes = [.init(
                id: "income", label: L10n.tr("Money in"),
                amountText: L10n.tr("\(Money.format(decision.annualIncome / 12)) a month"), dates: nil
            )]
        }
        if profile.housing == nil, let decision { profile.housing = housingText(decision, rent: collected.profile?.monthlyRent) }
        if let spending = collected.spending {
            profile.spending = spendSlices(spending)
            if !profile.spending.isEmpty {
                profile.spendingTotalText = spendingTotalText(spending, currentMonth: collected.currentMonth)
                profile.periodText = periodText(month: spending.month, currentMonth: collected.currentMonth)
            }
        }
        if let spending = collected.spending, !collected.billPayments.isEmpty {
            // The payments in the chart's month: their total equals the chart's bills and subscriptions slices.
            let rows = paidRows(collected.billPayments)
            profile.bills = rows
            let total = collected.billPayments.reduce(0) { $0 + $1.total }
            profile.billsTotalText = amountInPeriod(Money.format(total), month: spending.month, currentMonth: collected.currentMonth)
        } else {
            // Older server or a failed call: the regular bills and subscriptions, each a month.
            let bills = (collected.bills?.items ?? []).filter { $0.kind != .subscription && $0.kind != .rent }.prefix(5).map { bill in
                OnboardingViewState.ProfileRow(
                    id: "bill." + bill.id, label: bill.name, valueText: Money.format(bill.amount),
                    detail: L10n.tr("Due \(FinanceMapping.dayText(bill.dueDate))")
                )
            }
            let subscriptions = (collected.subscriptions?.items ?? []).prefix(5).map { item in
                OnboardingViewState.ProfileRow(
                    id: "sub." + item.id, label: item.merchant,
                    valueText: L10n.tr("\(Money.format(item.monthlyCost)) a month"), detail: L10n.tr("Subscription")
                )
            }
            profile.bills = Array(bills) + Array(subscriptions)
        }
        if collected.overview != nil || decision != nil {
            profile.debts = debtRows(overview: collected.overview, profile: collected.profile)
            profile.noDebts = profile.debts.isEmpty
        }
        if let decision {
            profile.savingsText = Money.format(decision.savings)
            let monthly = profile.spending.reduce(0) { $0 + $1.amount }
            if let months = collected.profile?.monthsOfCover {
                profile.coverText = L10n.tr("About \(NextMoveViewModel.monthsText(months)) of spending")
            } else if monthly > 0 {
                profile.coverText = L10n.tr("About \(NextMoveViewModel.monthsText(decision.savings / monthly)) of spending")
            }
        }
        if let habits = collected.habits {
            profile.habitOverall = habits.overall
            profile.habitParts = habitParts(habits)
        }
        if let facts = collected.profile {
            // No "Sample data" tag (B4): the facts come from the statement or the typed numbers.
            let source = facts.meta.source == "manual" ? L10n.tr("From the numbers you typed") : L10n.tr("From their statement")
            profile.noticed = facts.personalFacts.prefix(3).map { fact in
                .init(
                    id: fact.id, text: fact.text, icon: noticedIcon(fact.conceptId),
                    evidence: evidenceRows(fact), sourceText: source
                )
            }
        }
        return profile
    }

    /// One row per bill or subscription payment in the month, newest first: "giffgaff", "£8", "Paid 5 Sep".
    static func paidRows(_ details: [CategoryDetail]) -> [OnboardingViewState.ProfileRow] {
        let rows = details.flatMap { detail in
            detail.transactions.map { transaction in
                let name = transaction.merchant.flatMap(nonEmpty) ?? transaction.description
                let paid = L10n.tr("Paid \(shortDay(transaction.date))")
                return (
                    date: transaction.date,
                    row: OnboardingViewState.ProfileRow(
                        id: "paid." + transaction.id, label: name, valueText: Money.format(abs(transaction.amount)),
                        detail: detail.category == .subscriptions ? L10n.tr("\(paid) · Subscription") : paid
                    )
                )
            }
        }
        return rows.sorted { $0.date > $1.date }.map(\.row)
    }

    /// "How Penny decides" (C8): money now (+ expected income), bills before the next money, the buffer, the next
    /// money, then the result. The numbers are the forecast's; each step lists its sources.
    static func makeDecides(_ forecast: Forecast) -> OnboardingViewState.Decides {
        let maths = ForecastMathsState.make(forecast)
        func step(_ id: Components.Schemas.ForecastStep.IdPayload) -> Components.Schemas.ForecastStep? {
            forecast.steps.first { $0.id == id }
        }
        func labels(_ sources: [Components.Schemas.ForecastSource]?) -> [String] {
            var seen = Set<String>()
            return (sources ?? []).map(\.label).filter { !$0.isEmpty && seen.insert($0).inserted }
        }
        var moneyDetail = (step(.moneyNow)?.text).flatMap(nonEmpty)
        var moneySources = labels(step(.moneyNow)?.sources)
        if forecast.incomeExpectedTotal > 0 {
            let before = forecast.nextMoneyIfAny.map { ForecastText.shortDate($0.date) } ?? ""
            let line = L10n.tr("Money now \(ForecastText.whole(forecast.moneyNow)) + expected before \(before) \(ForecastText.whole(forecast.incomeExpectedTotal))")
            moneyDetail = [line, moneyDetail].compactMap { $0 }.joined(separator: ". ")
            for label in labels(forecast.incomeExpected.map(\.source)) where !moneySources.contains(label) { moneySources.append(label) }
        }
        let details: [String?] = [
            moneyDetail,
            (step(.bills)?.text).flatMap(nonEmpty),
            (step(.buffer)?.text).flatMap(nonEmpty),
            forecast.nextMoneyIfAny.map(\.label),
        ]
        let sources: [[String]] = [
            moneySources,
            labels(step(.bills)?.sources),
            labels(step(.buffer)?.sources),
            forecast.nextMoneyIfAny.map { labels([$0.source]) } ?? [],
        ]
        let steps = maths.steps.enumerated().map { index, item in
            OnboardingViewState.DecideStep(
                number: item.number, title: item.title, amountText: item.amountText,
                detail: index < details.count ? details[index] : nil,
                sources: index < sources.count ? sources[index] : []
            )
        }
        let verdict: String = switch forecast.state {
        case .onTrack: L10n.tr("On track")
        case .runningShort: L10n.tr("Running short")
        case .noNextMoney: L10n.tr("No money due yet")
        }
        return .init(
            question: L10n.tr("Will their money last until their next money arrives?"),
            steps: steps,
            sumLine: maths.sum?.line,
            resultText: maths.sum?.result,
            dailyText: maths.sum?.daily,
            habitText: maths.habits?.text,
            habitSource: maths.habits?.source,
            verdict: verdict
        )
    }
}
