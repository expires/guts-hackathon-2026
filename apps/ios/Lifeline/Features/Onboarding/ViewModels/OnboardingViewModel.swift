import Foundation
import Observation

/// Onboarding flow (ADR 0029). Every number on the reveal and the tips comes from the engine
/// (`GET /v1/next-move`, `GET /v1/finance/profile`) after the user's data is in.
@MainActor
@Observable
final class OnboardingViewModel {
    static let maxStatementBytes = 5 * 1024 * 1024

    private let api: OnboardingAPI
    /// Time between two import stages in the animation. Tests use zero.
    private let stageDelay: Duration
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

    /// Where the flow opened. From `.connect`, Back on "Connect your money" closes onboarding.
    let startAt: OnboardingStep

    init(
        api: OnboardingAPI,
        appleAvailable: Bool,
        isSampleData: Bool,
        startAt: OnboardingStep = .welcome,
        now: Date = Date(),
        stageDelay: Duration = .milliseconds(550)
    ) {
        self.api = api
        self.startAt = startAt
        self.stageDelay = stageDelay
        let year = Calendar(identifier: .gregorian).component(.year, from: now)
        let month = Calendar(identifier: .gregorian).component(.month, from: now)
        state = OnboardingViewState(
            signIn: .init(appleAvailable: appleAvailable),
            manual: .init(dealEndYear: year + 1, dealEndMonth: month, dealEndYears: year...(year + 10)),
            isSampleData: isSampleData
        )
        if startAt == .connect { state.step = .connect }
    }

    var actions: OnboardingActions {
        OnboardingActions(
            onNext: { [weak self] in self?.next() },
            onBack: { [weak self] in self?.back() },
            onSkipWelcome: { [weak self] in self?.go(.signIn) },
            onSignInWithApple: { [weak self] in Task { await self?.signInWithApple() } },
            onContinueWithoutAccount: { [weak self] in self?.continueWithoutAccount() },
            onConnect: { [weak self] kind in Task { await self?.connect(kind) } },
            onManualChange: { [weak self] manual in self?.updateManual(manual) },
            onAddCost: { [weak self] in self?.addCost() },
            onRemoveCost: { [weak self] id in self?.removeCost(id) },
            onUseLocation: { [weak self] in Task { await self?.useLocation() } },
            onSaveManual: { [weak self] in Task { await self?.saveManual() } },
            onPickSample: { [weak self] id in Task { await self?.importSample(id) } },
            onToggleIncome: { [weak self] id in self?.toggleIncome(id) },
            onToggleDebt: { [weak self] id in self?.toggleDebt(id) },
            onFinish: { [weak self] in self?.finish() },
            onDismissError: { [weak self] in self?.state.errorMessage = nil }
        )
    }

    // MARK: Navigation

    func next() {
        switch state.step {
        case let .welcome(page):
            go(page + 1 < state.pages.count ? .welcome(page: page + 1) : .signIn)
        case .reveal:
            if state.tips.isEmpty { finish() } else { go(.tips) }
        case .tips:
            finish()
        default:
            break
        }
    }

    func back() {
        switch state.step {
        case let .welcome(page) where page > 0: go(.welcome(page: page - 1))
        case .signIn: go(.welcome(page: state.pages.count - 1))
        case .connect: if startAt == .connect { finish() } else { go(.signIn) }
        case .manual, .samples: go(.connect)
        default: break
        }
    }

    func go(_ step: OnboardingViewState.Step) {
        state.errorMessage = nil
        state.step = step
    }

    func finish() {
        onFinished()
    }

    // MARK: Sign in

    func signInWithApple() async {
        guard state.signIn.appleAvailable, let appleSignIn else {
            continueWithoutAccount(note: "Sign in with Apple is not set up in this build. You use a demo account on this phone.")
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
            continueWithoutAccount(note: "Sign in with Apple did not work. You use a demo account on this phone.")
        }
    }

    /// Demo sign-in: the client signs in with the device id on the first request.
    func continueWithoutAccount(note: String? = nil) {
        state.signIn.note = note
        go(.connect)
        state.errorMessage = nil
    }

    // MARK: Connect your money

    func connect(_ kind: OnboardingViewState.ConnectOption.Kind) async {
        state.errorMessage = nil
        switch kind {
        case .sample:
            go(.samples)
            await loadSamples()
        case .monzo: await connectMonzo()
        case .trading212:
            if api.hasTrading212 { break }
            markUnavailable(.trading212)
            state.errorMessage = "Trading 212 is not available yet. Upload a statement or enter your numbers."
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
            state.errorMessage = "Monzo was not connected. Try again, or use another way."
        }
    }

    private func monzoUnavailable() {
        markUnavailable(.monzo)
        state.errorMessage = "Monzo is unavailable right now. Upload a statement or enter your numbers."
    }

    /// `lifeline://connected?status=ok|error&session=...`
    func bankCallback(_ url: URL) async {
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        let status = items.first { $0.name == "status" }?.value
        guard status == "ok", let session = items.first(where: { $0.name == "session" })?.value else {
            state.errorMessage = "Monzo was not connected. Try again, or use another way."
            return
        }
        startImporting(title: "Importing your history", labels: [
            ("bank", "Reading your Monzo account"),
            ("next_move", "Finding your next move"),
        ])
        do {
            _ = try await api.bankSummary(session)
            await completeStage(0)
            await loadReveal(stageIndex: 1)
        } catch {
            failImport(error)
        }
    }

    // MARK: Sample statements

    /// The 4 student cards (team profiles hidden). Cached first, so they show at once (ADR 0060).
    func loadSamples() async {
        if state.samples.isEmpty { state.samplesLoading = true }
        defer { state.samplesLoading = false }
        do {
            try await api.listSamples { [weak self] samples in
                self?.state.samples = Self.sampleCards(samples)
                self?.state.samplesLoading = false
            }
        } catch {
            if state.samples.isEmpty { state.errorMessage = APIError.map(error).userMessage }
        }
    }

    static func sampleCards(_ samples: [SampleStatement]) -> [OnboardingViewState.SampleCard] {
        samples.filter { $0.team != true }.map { sample in
            .init(
                id: sample.id,
                title: sample.title,
                text: sample.description,
                fundingText: sample.funding.map { fundingLabel($0.rawValue) }.joined(separator: " · "),
                monthsText: sample.months == 1 ? "1 month of payments" : "\(sample.months) months of payments"
            )
        }
    }

    static func fundingLabel(_ raw: String) -> String {
        OnboardingViewState.IncomeRow.Kind(rawValue: raw)?.label ?? raw.replacingOccurrences(of: "_", with: " ").capitalized
    }

    /// Imports the sample student's statement through the real pipeline, then shows the reveal.
    func importSample(_ id: String) async {
        state.step = .importing
        state.importing = .init(title: "Importing your history")
        do {
            let result = try await api.importSample(id)
            await showImport(result)
        } catch {
            failImport(error)
        }
    }

    // MARK: Statement

    func importStatement(data: Data, fileName: String) async {
        guard data.count <= Self.maxStatementBytes else {
            state.errorMessage = "This file is larger than 5 MB. Export a shorter period and try again."
            return
        }
        let provider: String? = fileName.lowercased().hasSuffix(".pdf") ? "pdf" : nil
        state.step = .importing
        state.importing = .init(title: "Importing your history")
        do {
            let result = try await api.importStatement(data, fileName, provider)
            await showImport(result)
        } catch {
            failImport(error)
        }
    }

    /// Animates the import stages, then loads the reveal. A failed import goes back to "Connect your money".
    private func showImport(_ result: Components.Schemas.ImportResult) async {
        guard result.status != .failed else {
            state.step = .connect
            state.errorMessage = (["We could not read this statement."] + (result.warnings ?? [])).joined(separator: " ")
            return
        }
        state.importing = Self.makeImporting(result, shown: 0)
        state.importing.isFinished = false
        for _ in result.stages {
            try? await Task.sleep(for: stageDelay)
            state.importing.shownCount += 1
        }
        await loadReveal(stageIndex: nil)
    }

    /// "412 payments, 1 Apr 2026 to 16 Oct 2026".
    static func importSummary(_ result: Components.Schemas.ImportResult) -> String {
        let count = result.transactions == 1 ? "1 payment" : "\(result.transactions) payments"
        guard let first = result.firstDate.flatMap(FinanceMapping.date), let last = result.lastDate.flatMap(FinanceMapping.date) else {
            return count
        }
        let format = Date.FormatStyle(date: .abbreviated, time: .omitted).locale(Money.locale)
        return "\(count), \(first.formatted(format)) to \(last.formatted(format))"
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
            state.manual.locationNote = "Location is not set up yet. Type your postcode."
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
            state.manual.locationNote = "We could not find your postcode. Type it instead."
        }
    }

    static func problems(_ manual: OnboardingViewState.Manual) -> [String] {
        var problems: [String] = []
        let postcode = manual.postcode.trimmingCharacters(in: .whitespaces)
        let allowed = CharacterSet.alphanumerics.union(.init(charactersIn: " "))
        if postcode.count < 5 || postcode.count > 8 || postcode.unicodeScalars.contains(where: { !allowed.contains($0) }) {
            problems.append("Enter a full UK postcode, for example LS6 1AN.")
        }
        if manual.isStudent {
            if !manual.incomes.contains(where: { $0.isOn && $0.amount > 0 }) {
                problems.append("Turn on at least one way money arrives and enter the amount.")
            }
        } else if manual.monthlyTakeHome <= 0 || manual.monthlyTakeHome > 1_000_000 {
            problems.append("Enter your take-home pay a month.")
        }
        if let age = manual.age, !(16...100).contains(age) {
            problems.append("Enter an age from 16 to 100.")
        } else if manual.age == nil {
            problems.append("Enter your age.")
        }
        switch manual.housing {
        case .rent:
            if manual.monthlyRent <= 0 || manual.monthlyRent > 100_000 { problems.append("Enter your rent a month.") }
        case .mortgage:
            if manual.mortgageBalance <= 0 { problems.append("Enter what you still owe on the mortgage.") }
            if manual.mortgageRatePercent <= 0 || manual.mortgageRatePercent > 30 { problems.append("Enter your mortgage rate, for example 4.4.") }
        case .own, .parents:
            break
        }
        if manual.costs.contains(where: { $0.name.trimmingCharacters(in: .whitespaces).isEmpty || $0.monthlyAmount < 0 }) {
            problems.append("Give every regular cost a name.")
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
        startImporting(title: "Saving your numbers", labels: [
            ("manual", "Saving your numbers"),
            ("next_move", "Finding your next move"),
        ])
        do {
            _ = try await api.setManualFinance(input)
            await completeStage(0)
            await loadReveal(stageIndex: 1)
        } catch {
            failImport(error)
        }
    }

    // MARK: Importing, reveal and tips

    private func startImporting(title: String, labels: [(String, String)]) {
        state.errorMessage = nil
        state.step = .importing
        state.importing = .init(title: title, stages: labels.map { .init(id: $0.0, label: $0.1, done: false) }, shownCount: labels.count)
    }

    private func completeStage(_ index: Int) async {
        guard state.importing.stages.indices.contains(index) else { return }
        try? await Task.sleep(for: stageDelay)
        state.importing.stages[index].done = true
    }

    /// Loads the top move and the personal facts, then shows the reveal.
    private func loadReveal(stageIndex: Int?) async {
        do {
            let response = try await api.nextMove()
            state.reveal = Self.makeReveal(response)
            if let profile = try? await api.financeProfile() {
                state.tips = Self.makeTips(profile)
            }
            if let stageIndex { await completeStage(stageIndex) }
            state.importing.isFinished = true
            try? await Task.sleep(for: stageDelay)
            state.step = .reveal
        } catch {
            failImport(error)
        }
    }

    /// The reveal card from the engine's top move (same mapping as the Money tab card).
    static func makeReveal(_ response: NextMoveResponse) -> OnboardingViewState.Reveal? {
        let card = NextMoveViewModel.makeState(response: response, phase: .ready)
        guard let move = card.displayedMove else { return nil }
        return .init(
            action: move.action,
            headline: move.headline,
            impactAmountText: move.impactAmountText,
            impactCaption: move.impactCaption,
            confidenceWord: move.confidenceWord,
            confidenceFilled: move.confidenceFilled,
            confidenceLabel: move.confidenceLabel,
            isSampleData: card.isSampleData
        )
    }

    /// The top 3 personal facts, in the engine's order.
    static func makeTips(_ profile: FinanceProfile) -> [OnboardingViewState.Tip] {
        profile.personalFacts.prefix(3).enumerated().map { .init(id: $1.id, number: $0 + 1, text: $1.text) }
    }

    /// The import screen for a finished statement import.
    static func makeImporting(_ result: Components.Schemas.ImportResult, shown: Int) -> OnboardingViewState.Importing {
        .init(
            title: "Importing your history",
            stages: result.stages.map { .init(id: $0.name.rawValue, label: $0.label, done: $0.done) },
            shownCount: shown,
            summary: importSummary(result),
            warnings: result.warnings ?? [],
            isFinished: shown >= result.stages.count
        )
    }

    private func failImport(_ error: Error) {
        let mapped = APIError.map(error)
        state.step = .connect
        state.errorMessage = mapped.isNoFinanceData
            ? "We could not build your profile from this. Try another way."
            : mapped.userMessage
    }
}
