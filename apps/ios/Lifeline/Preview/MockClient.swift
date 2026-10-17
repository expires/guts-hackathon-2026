import Foundation

/// In-memory client built from the contract examples (ADR 0011).
/// Returns at once and never calls the network. It simulates AGE, choices, actions and rewind
/// well enough for the UI test flow and the Playground.
///
/// Every number it returns comes from the contract examples or from the example deltas.
actor MockClient: LifelineClient {
    /// In-memory Circles for the Mock configuration.
    private var circles: [PlayCircle] = []
    nonisolated let kind = ClientKind.mock
    private var lives: [String: Life] = [:]
    private var nextLifeNumber = 1
    /// Per life: template id -> last game year it fired (engine cooldown, `EVENT_COOLDOWN_YEARS`).
    private var firedEvents: [String: [String: Int]] = [:]
    /// Per life: position in `MockExamples.eventPool` to try next.
    private var nextEventSlot: [String: Int] = [:]
    private var nextRoomPlayer = 2
    private var budgetLimits: [String: Double] = [:]
    private var createdGoals: [SavingsGoal] = []
    /// Guesses made in this session, by date (YYYY-MM-DD). One per day (ADR 0017).
    private var guessesByDate: [String: Double] = [:]
    private var planItems: [PlanItem] = []
    private var chatThreads: [String: ChatThread] = [:]
    private var nextChatNumber = 1
    private var me: Me = MockExamples.me
    private let data: MockData
    /// Gap between streamed chat events. Tests can set it to zero.
    let streamGap: Duration

    /// - Parameter data: `.contract` (default: tests, previews, Playground) or `.recorded` (the app's mock mode).
    init(data: MockData = .contract, streamGap: Duration = .milliseconds(400)) {
        self.data = data
        self.streamGap = streamGap
        let contract = MockData.contract
        self.usesRecordedData = data.financeOverview != contract.financeOverview
            || data.nextMove != contract.nextMove
            || data.characters != contract.characters
    }

    /// True for `MockData.recorded` (some recorded file differs from the contract). Contract mode never reads
    /// `Preview/Recorded/*` directly, so tests, previews and the Playground see contract examples only.
    private let usesRecordedData: Bool

    // MARK: Lives

    func listCharacters(seed: Int?) async throws -> CharactersResponse {
        data.characters
    }

    func createLife(_ request: CreateLifeRequest) async throws -> Life {
        let character: CharacterSpec
        switch request.mode {
        case .preset:
            guard let found = data.characters.presets.first(where: { $0.id == request.presetId }) else {
                throw APIError.server(status: 404, code: "not_found", message: "That character does not exist.", source: "mock")
            }
            character = found
        case .random:
            character = data.characters.random
        case ._self, .god:
            guard let provided = request.character else {
                throw APIError.server(status: 422, code: "validation_error", message: "character: required", source: "mock")
            }
            character = provided
        }

        var life = data.life
        life.id = String(format: "lf_mock%02d", nextLifeNumber)
        nextLifeNumber += 1
        life.mode = Life.ModePayload(rawValue: request.mode.rawValue) ?? .preset
        life.character = character
        life.startYear = request.startYear
        life.year = request.startYear
        life.age = max(0, request.startYear - character.birthYear)
        var job = life.job ?? .init(title: character.occupation, annualIncome: character.annualIncome)
        job.title = character.occupation.capitalized
        job.annualIncome = character.annualIncome
        life.job = job
        life.finances.annualIncome = character.annualIncome
        life.history = [
            YearLog(
                year: life.year,
                age: life.age,
                text: "You start life in \(character.town).",
                netWorth: life.finances.netWorth,
                autopilotNetWorth: life.finances.netWorth,
                index: life.index.value
            ),
        ]
        lives[life.id] = life
        return life
    }

    func getLife(id: String) async throws -> Life {
        try stored(id)
    }

    func age(lifeID: String) async throws -> AgeResult {
        var life = try stored(lifeID)
        guard life.alive else {
            throw APIError.server(status: 409, code: "dead", message: "This life is over.", source: "mock")
        }
        guard life.pendingEvents.isEmpty else {
            throw APIError.server(status: 409, code: "pending_events", message: "Answer the open events before you age.", source: "mock")
        }
        life.year += 1
        life.age += 1
        if life.age >= 90 {
            life.alive = false
            life.causeOfDeath = "Old age"
            lives[lifeID] = life
            return AgeResult(life: life, events: [])
        }
        guard var event = nextEvent(lifeID: lifeID, year: life.year) else {
            lives[lifeID] = life
            return AgeResult(life: life, events: [])
        }
        event.id = "ev-\(life.year)-1"
        event.year = life.year
        event.age = life.age
        life.pendingEvents = [event]
        lives[lifeID] = life
        return AgeResult(life: life, events: [event])
    }

    func choose(lifeID: String, eventID: String, choiceID: String) async throws -> ChoiceResult {
        var life = try stored(lifeID)
        guard let event = life.pendingEvents.first(where: { $0.id == eventID }),
              event.choices.contains(where: { $0.id == choiceID }) else {
            throw APIError.server(status: 409, code: "no_such_event", message: "That event is no longer open.", source: "mock")
        }
        // The contract has an example result for "move" and for the default choice "accept".
        let example = choiceID == ContractExamples.choiceResult.outcome.choiceId
            ? ContractExamples.choiceResult
            : ContractExamples.choiceResultDefault
        var outcome = example.outcome
        outcome.eventId = eventID
        outcome.choiceId = choiceID
        apply(outcome.deltas, to: &life)
        life.pendingEvents.removeAll { $0.id == eventID }
        life.history.append(
            YearLog(
                year: life.year,
                age: life.age,
                text: "\(event.title). \(outcome.text)",
                decisionId: eventID,
                eventId: eventID,
                choiceId: choiceID,
                netWorth: life.finances.netWorth,
                autopilotNetWorth: life.history.last?.autopilotNetWorth ?? life.finances.netWorth,
                index: life.index.value
            )
        )
        let lesson = example.lesson
        let isNewConcept = lesson.map { !life.conceptsUnlocked.contains($0.conceptId) } ?? false
        if isNewConcept, let lesson { life.conceptsUnlocked.append(lesson.conceptId) }
        lives[lifeID] = life
        return ChoiceResult(
            life: life,
            outcome: outcome,
            lesson: isNewConcept ? lesson : nil,
            conceptUnlocked: isNewConcept ? lesson?.conceptId : nil
        )
    }

    func act(lifeID: String, request: ActionRequest) async throws -> ActionResult {
        var life = try stored(lifeID)
        guard let action = life.availableActions.first(where: { $0.id == request.actionId }) else {
            throw APIError.server(status: 409, code: "no_such_action", message: "You cannot do that right now.", source: "mock")
        }
        if action.paid == true {
            throw APIError.server(status: 402, code: "payment_required", message: "This needs a paid extra (Demo payment).", source: "mock")
        }
        var outcome = ContractExamples.actionResult.outcome
        outcome.choiceId = action.id
        outcome.text = action.id == ContractExamples.actionResult.outcome.choiceId
            ? outcome.text
            : "You chose: \(action.label)."
        apply(outcome.deltas, to: &life)
        life.history.append(
            YearLog(
                year: life.year,
                age: life.age,
                text: outcome.text,
                netWorth: life.finances.netWorth,
                autopilotNetWorth: life.history.last?.autopilotNetWorth ?? life.finances.netWorth,
                index: life.index.value
            )
        )
        lives[lifeID] = life
        return ActionResult(life: life, outcome: outcome)
    }

    func rewind(lifeID: String, decisionID: String) async throws -> RewindResult {
        var life = try stored(lifeID)
        guard let position = life.history.firstIndex(where: { $0.decisionId == decisionID }) else {
            throw APIError.server(status: 404, code: "not_found", message: "That choice is not in this life.", source: "mock")
        }
        guard life.rewind.freeLeft > 0 || life.rewind.hasPass == true else {
            throw APIError.server(status: 402, code: "payment_required", message: "Free rewind used. Rewind Pass needed (Demo payment).", source: "mock")
        }
        let abandonedIndex = life.index.value
        let abandonedNetWorth = life.finances.netWorth
        let target = life.history[position]
        life.history = Array(life.history[..<position])
        life.year = target.year
        life.age = target.age
        life.alive = true
        life.causeOfDeath = nil
        life.finances.netWorth = life.history.last?.netWorth ?? target.netWorth
        var event = ContractExamples.event
        event.id = decisionID
        event.year = target.year
        event.age = target.age
        life.pendingEvents = [event]
        if life.rewind.hasPass != true { life.rewind.freeLeft -= 1 }
        lives[lifeID] = life
        return RewindResult(life: life, abandonedIndex: abandonedIndex, abandonedNetWorth: abandonedNetWorth)
    }

    func summary(lifeID: String) async throws -> LifeSummary {
        guard let life = lives[lifeID] else { return data.summary }
        var summary = data.summary
        summary.lifeId = life.id
        summary.name = life.character.name
        summary.born = life.character.birthYear
        summary.died = life.alive ? nil : life.year
        summary.age = life.age
        summary.causeOfDeath = life.causeOfDeath
        summary.finalIndex = life.index.value
        summary.netWorth = life.finances.netWorth
        summary.autopilotNetWorth = life.history.last?.autopilotNetWorth ?? life.finances.netWorth
        summary.ribbons = life.ribbons
        summary.conceptsUnlocked = life.conceptsUnlocked.count
        summary.timeline = life.history
        return summary
    }

    func listLives() async throws -> LivesResponse {
        var response = data.lives
        let mine = lives.values.sorted { $0.id < $1.id }.map { life in
            LifeListItem(
                id: life.id,
                name: life.character.name,
                emoji: life.character.emoji ?? "🙂",
                mode: life.mode.rawValue,
                year: life.year,
                age: life.age,
                alive: life.alive,
                index: life.index.value,
                netWorth: life.finances.netWorth,
                ribbons: life.ribbons.count
            )
        }
        response.lives = mine + response.lives
        return response
    }

    // MARK: Money tab

    func financeOverview() async throws -> FinanceOverview { data.financeOverview }

    /// No finance data (after reset or delete): the contract `FinanceHomeEmpty` example.
    /// Recorded mode: `Recorded/getFinanceHome.json` when present. Otherwise built from `data`
    /// (contract mode: the contract examples for overview, next move, prediction and bills).
    func financeHome() async throws -> FinanceHome {
        guard me.hasFinanceData else { return MockExamples.financeHomeEmpty }
        if usesRecordedData, let recorded = MockExamples.recordedFinanceHome { return recorded }
        let bills = data.bills.items
        return FinanceHome(
            hasData: true,
            meta: data.financeOverview.meta,
            balance: data.financeOverview.balance,
            netWorth: data.financeOverview.netWorth,
            nextMove: data.nextMove,
            prediction: try await spendPrediction(date: nil),
            comingUp: Array(bills.prefix(3)),
            comingUpMore: bills.count > 3
        )
    }
    func financeSpending(month: String?) async throws -> SpendingResponse { data.spending }
    func subscriptions() async throws -> SubscriptionsResponse { data.subscriptions }
    func bills() async throws -> BillsResponse { data.bills }

    func budgets(month: String?) async throws -> BudgetsResponse {
        var response = data.budgets
        response.items = response.items.map { budget in
            guard let limit = budgetLimits[budget.category.rawValue] else { return budget }
            var updated = budget
            updated.limit = limit
            updated.progress = limit > 0 ? budget.spent / limit : 0
            updated.status = updated.progress > 1 ? .over : (updated.progress >= 0.8 ? .near : .ok)
            return updated
        }
        return response
    }

    func updateBudgets(_ limits: [BudgetLimit]) async throws -> BudgetsResponse {
        for limit in limits { budgetLimits[limit.category.rawValue] = limit.limit }
        return try await budgets(month: nil)
    }

    func goals() async throws -> GoalsResponse {
        var response = data.goals
        response.items += createdGoals
        return response
    }

    func createGoal(_ request: CreateGoalRequest) async throws -> SavingsGoal {
        let saved = request.saved ?? 0
        let goal = SavingsGoal(
            id: "goal_mock\(createdGoals.count + 1)",
            name: request.name,
            emoji: request.emoji ?? "🎯",
            target: request.target,
            saved: saved,
            progress: request.target > 0 ? saved / request.target : 0,
            targetDate: request.targetDate
        )
        createdGoals.append(goal)
        return goal
    }

    func financeProfile() async throws -> FinanceProfile { data.financeProfile }

    /// Today: the contract example without a guess until the user guesses.
    /// A past day from the guesses example: that day's guess, prediction, range and actual.
    func spendPrediction(date: String?) async throws -> SpendPrediction {
        let today = data.spendPrediction.date
        let day = date ?? today
        if day != today, let past = data.guesses.items.first(where: { $0.date == day }) {
            var prediction = data.spendPredictionBeforeGuess
            prediction.date = day
            prediction.predicted = past.predicted
            prediction.actual = past.actual
            if let backtest = data.predictionEvaluation.days.first(where: { $0.date == day }) {
                prediction.low = backtest.low
                prediction.high = backtest.high
                prediction.baseline = backtest.baseline
            }
            prediction.reasons = []
            prediction.guess = .init(amount: past.guess, madeAt: "\(day)T08:00:00Z", points: past.points, beatModel: past.beatModel)
            return prediction
        }
        var prediction = data.spendPredictionBeforeGuess
        prediction.date = day
        if let amount = guessesByDate[day] {
            prediction.guess = .init(amount: amount, madeAt: data.spendPrediction.guess?.madeAt ?? "\(day)T08:00:00Z")
        }
        return prediction
    }

    func guesses() async throws -> GuessesResponse { data.guesses }

    func makeGuess(date: String, amount: Double) async throws -> SpendPrediction {
        guard guessesByDate[date] == nil else {
            throw APIError.server(status: 409, code: "already_guessed", message: "You already guessed for this day.", source: "mock")
        }
        guessesByDate[date] = amount
        return try await spendPrediction(date: date)
    }

    func predictionEvaluation() async throws -> PredictionEvaluation { data.predictionEvaluation }

    // MARK: Next Move

    func nextMove() async throws -> NextMoveResponse { data.nextMove }

    func testNextMove(moveID: String, optionIDs: [String]?) async throws -> TestMoveResult {
        guard moveID == data.testMoveResult.moveId else {
            throw APIError.server(status: 404, code: "not_found", message: "That move cannot be tested.", source: "mock")
        }
        var result = data.testMoveResult
        if let optionIDs, !optionIDs.isEmpty {
            let kept = result.outcomes.filter { optionIDs.contains($0.optionId) }
            if !kept.isEmpty { result.outcomes = kept }
        }
        return result
    }

    func plan() async throws -> PlanResponse {
        PlanResponse(items: planItems, totalImpactPerYear: planItems.reduce(0) { $0 + $1.impactPerYear })
    }

    func addPlanItem(moveID: String) async throws -> PlanItem {
        if let existing = planItems.first(where: { $0.moveId == moveID }) { return existing }
        let response = data.nextMove
        guard let move = ([response.top] + response.runnersUp).first(where: { $0.id == moveID }) else {
            throw APIError.server(status: 404, code: "not_found", message: "That move does not exist.", source: "mock")
        }
        let item = PlanItem(
            id: "pl_\(planItems.count + 1)",
            moveId: move.id,
            kind: PlanItem.KindPayload(rawValue: move.kind.rawValue) ?? .fixMortgage,
            action: move.action,
            impactPerYear: move.impactPerYear,
            addedAt: ContractExamples.planItem.addedAt,
            status: .todo
        )
        planItems.append(item)
        return item
    }

    // MARK: Learn

    func listConcepts() async throws -> [Concept] { data.concepts }
    func listChallenges() async throws -> [Challenge] { data.challenges }

    // MARK: Decision

    func createDecision(profile: DecisionProfile, lifeID: String?) async throws -> Decision { ContractExamples.decision }
    func evaluation() async throws -> Evaluation { data.evaluation }

    // MARK: Meta

    func listSources() async throws -> [SourceStatus] { data.sources }

    // MARK: Rooms

    func createRoom(_ request: CreateRoomRequest) async throws -> Room {
        var room = ContractExamples.room
        room.mode = request.mode.flatMap { Room.ModePayload(rawValue: $0.rawValue) } ?? .duel
        room.presetId = request.presetId
        room.startYear = request.startYear
        room.players = [.init(id: "p1", name: request.hostName ?? "You", isHost: true, finished: false)]
        return room
    }

    func listPaths() async throws -> [StudentPath] {
        [
            .init(id: "uni", title: "University", description: "3-year degree with a maintenance loan", startAge: 18, quick: true),
            .init(id: "apprentice", title: "Apprenticeship", description: "Earn while you learn", startAge: 18, quick: true),
            .init(id: "job18", title: "Job at 18", description: "Start work straight after school", startAge: 18, quick: true),
            .init(id: "gap_year", title: "Gap year", description: "Work and travel, then decide", startAge: 18, quick: true),
            .init(id: "masters", title: "Master's", description: "One more year of study after a degree", startAge: 21, quick: false),
        ]
    }

    func listCircles() async throws -> [PlayCircle] { circles }

    func createCircle(name: String) async throws -> PlayCircle {
        let circle = PlayCircle(id: "c_\(circles.count + 1)", name: name, code: "Q7K2P\(circles.count)", members: [])
        circles.append(circle)
        return circle
    }

    func joinCircle(code: String) async throws -> PlayCircle {
        if let found = circles.first(where: { $0.code == code }) { return found }
        throw APIError.server(status: 404, code: "not_found", message: "No Circle with that code.", source: "mock")
    }

    func leaveCircle(id: String) async throws { circles.removeAll { $0.id == id } }

    func getRoom(code: String) async throws -> Room {
        var room = ContractExamples.room
        room.code = code
        return room
    }

    /// Simulated room: the caller is joined with 3 rivals who move one year for every `progress` the caller sends.
    nonisolated func roomSocket(code: String) async throws -> RoomSocket {
        MockRoomSimulator.socket(code: code, gap: streamGap)
    }

    // MARK: Account

    func getMe() async throws -> Me { me }

    func deleteAccount() async throws {
        me = MockExamples.me
        me.hasFinanceData = false
        me.financeInputs = []
    }

    func resetDemo() async throws -> Me {
        lives = [:]
        planItems = []
        guessesByDate = [:]
        chatThreads = [:]
        me.hasFinanceData = false
        me.financeInputs = []
        return me
    }

    func signOut() async throws {}

    func signInWithApple(identityToken: String) async throws {
        me.authProvider = .apple
    }

    // MARK: Onboarding inputs

    func importStatement(file: Data, fileName: String, provider: String?) async throws -> ImportResult {
        guard !file.isEmpty else {
            throw APIError.server(status: 422, code: "validation_error", message: "The file is empty.", source: "mock")
        }
        var result = MockExamples.importResult
        if let provider, let value = ImportResult.ProviderPayload(rawValue: provider) { result.provider = value }
        markFinanceInput(.statement)
        return result
    }

    func setManualFinance(_ input: ManualFinanceInput) async throws -> FinanceProfile {
        markFinanceInput(.manual)
        return data.financeProfile
    }

    func logPayment(_ request: LogPaymentRequest) async throws -> LoggedPayment {
        var logged = MockExamples.loggedPayment
        logged.transaction.amount = -request.amount
        logged.transaction.merchant = request.merchant
        logged.transaction.description = request.merchant
        if let date = request.date { logged.transaction.date = date }
        if let category = request.category, let value = LoggedPayment.CategoryPayload(rawValue: category.rawValue) {
            logged.category = value
        }
        markFinanceInput(.appIntent)
        return logged
    }

    func listSamples() async throws -> [SampleStatement] { MockExamples.samples }

    func importSample(id: String) async throws -> ImportResult {
        guard MockExamples.samples.contains(where: { $0.id == id }) else {
            throw APIError.server(status: 404, code: "not_found", message: "That sample does not exist.", source: "mock")
        }
        markFinanceInput(.statement)
        return MockExamples.importResult
    }

    func habits() async throws -> HabitScore { MockExamples.habits }

    func reversePostcode(lat: Double, lon: Double) async throws -> ReversePostcode { MockExamples.reversePostcode }

    func setHealthSignal(_ signal: HealthSignal) async throws -> HealthSignalStored {
        var stored = MockExamples.healthSignalStored
        stored.stepsPerDay = signal.stepsPerDay
        stored.sleepHours = signal.sleepHours
        stored.measuredDays = signal.measuredDays
        return stored
    }

    // MARK: Ask Penny

    func askPenny(_ request: ChatRequest) async throws -> ChatResponse {
        let response = MockExamples.chatResponse(for: request, threadID: request.threadId ?? newThreadID(), messageNumber: nextChatNumber)
        nextChatNumber += 2
        store(request: request, response: response)
        return response
    }

    /// Reaction, 2 tool steps, verifying, one bubble every `streamGap`, then done.
    nonisolated func askPennyStream(_ request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, any Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    let response = try await self.askPenny(request)
                    let gap = self.streamGap
                    let start = ContinuousClock.now
                    var seq = 0
                    func emit(_ event: ChatStreamEvent) {
                        var event = event
                        event.seq = seq
                        let elapsed = ContinuousClock.now - start
                        event.elapsedMs = Int(elapsed.components.seconds * 1000 + elapsed.components.attoseconds / 1_000_000_000_000_000)
                        seq += 1
                        continuation.yield(event)
                    }
                    try await Task.sleep(for: gap / 2)
                    emit(.init(_type: .reaction, seq: 0, elapsedMs: 0, reaction: .init(rawValue: response.reaction.rawValue)))
                    for step in MockExamples.toolSteps(for: response) {
                        try await Task.sleep(for: gap)
                        emit(.init(_type: .toolStep, seq: 0, elapsedMs: 0, step: step))
                    }
                    try await Task.sleep(for: gap)
                    emit(.init(_type: .verifying, seq: 0, elapsedMs: 0))
                    for bubble in response.bubbles {
                        try await Task.sleep(for: gap)
                        let highlights = response.highlights?.filter { $0.bubbleId == bubble.id }
                        emit(.init(_type: .bubble, seq: 0, elapsedMs: 0, bubble: .init(bubble: bubble, highlights: highlights)))
                    }
                    try await Task.sleep(for: gap / 2)
                    emit(.init(_type: .done, seq: 0, elapsedMs: 0, response: response))
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    func listChatThreads() async throws -> ChatThreadsResponse {
        guard !chatThreads.isEmpty else { return MockExamples.chatThreads }
        let mine = chatThreads.values.sorted { $0.id > $1.id }.map { thread in
            ChatThreadSummary(
                id: thread.id,
                title: thread.title,
                updatedAt: thread.messages.last?.createdAt ?? MockExamples.now,
                messageCount: thread.messages.count
            )
        }
        return ChatThreadsResponse(threads: mine)
    }

    func getChatThread(id: String) async throws -> ChatThread {
        if let thread = chatThreads[id] { return thread }
        if id == MockExamples.chatThread.id { return MockExamples.chatThread }
        throw APIError.server(status: 404, code: "not_found", message: "That chat does not exist.", source: "mock")
    }

    func listNews(from: String, to: String, topic: String?) async throws -> NewsResponse { MockExamples.news }

    func getRateDecisions() async throws -> RateDecisions { MockExamples.rateDecisions }

    // MARK: Bank

    func bankAuthLink(provider: String) async throws -> BankAuthLink { ContractExamples.bankAuthLink }
    func bankSummary(session: String) async throws -> BankSummary { ContractExamples.bankSummary }

    // MARK: Store

    func verifyPurchase(product: PurchaseProduct) async throws -> PurchaseVerifyResponse {
        var response = ContractExamples.purchase
        response.productId = product.rawValue
        switch product {
        case .lifeline_rewindpass: response.entitlement = .rewindPass
        case .lifeline_godmode: response.entitlement = .godMode
        case .lifeline_bossmode: response.entitlement = .bossMode
        }
        return response
    }

    // MARK: Helpers

    /// Next event from `MockExamples.eventPool`, in order, skipping any template that fired in the last
    /// `MockExamples.eventCooldownYears - 1` years (engine rule: not in Y+1 or Y+2). nil: no event this year.
    private func nextEvent(lifeID: String, year: Int) -> LifeEvent? {
        let pool = MockExamples.eventPool
        guard !pool.isEmpty else { return nil }
        var fired = firedEvents[lifeID] ?? [:]
        let start = nextEventSlot[lifeID] ?? 0
        for offset in 0..<pool.count {
            let slot = (start + offset) % pool.count
            let candidate = pool[slot]
            if let last = fired[candidate.templateId], year - last < MockExamples.eventCooldownYears { continue }
            fired[candidate.templateId] = year
            firedEvents[lifeID] = fired
            nextEventSlot[lifeID] = slot + 1
            return candidate
        }
        return nil
    }

    private func markFinanceInput(_ input: Me.FinanceInputsPayloadPayload) {
        me.hasFinanceData = true
        if !me.financeInputs.contains(input) { me.financeInputs.append(input) }
    }

    private func newThreadID() -> String {
        "th_mock\(chatThreads.count + 1)"
    }

    private func store(request: ChatRequest, response: ChatResponse) {
        var thread = chatThreads[response.threadId]
            ?? ChatThread(id: response.threadId, title: String(request.message.prefix(120)), messages: [])
        thread.messages.append(ChatMessage(
            id: response.replyTo,
            role: .user,
            createdAt: MockExamples.now,
            text: request.message,
            replyTo: request.replyTo,
            replies: 1
        ))
        thread.messages.append(ChatMessage(
            id: response.messageId,
            role: .penny,
            createdAt: MockExamples.now,
            replyTo: response.replyTo,
            response: response
        ))
        chatThreads[response.threadId] = thread
    }

    private func stored(_ id: String) throws -> Life {
        guard let life = lives[id] else {
            throw APIError.server(status: 404, code: "not_found", message: "Life \(id) not found.", source: "mock")
        }
        return life
    }

    private func apply(_ deltas: Components.Schemas.Deltas, to life: inout Life) {
        let money = deltas.money ?? 0
        life.finances.netWorth += money
        life.finances.cash += money
        life.stats.happiness = clamp(life.stats.happiness + (deltas.happiness ?? 0))
        life.stats.health = clamp(life.stats.health + (deltas.health ?? 0))
        life.stats.smarts = clamp(life.stats.smarts + (deltas.smarts ?? 0))
    }

    private func clamp(_ value: Int) -> Int { min(100, max(0, value)) }
}

/// Contract examples for the account, onboarding and chat operations (`components.examples`).
enum MockExamples {
    static let now = "2026-10-17T12:00:00Z"

    /// Engine rule (`lifeline_sim/params.py` EVENT_COOLDOWN_YEARS): a template that fired in year Y
    /// cannot fire again in Y+1 or Y+2.
    static let eventCooldownYears = 3

    /// Events for AGE: the contract example first (tests rely on it), then real engine events recorded
    /// into `Preview/Recorded/ageLife.json`, one per template.
    static let eventPool: [LifeEvent] = {
        var pool = [ContractExamples.event]
        if let url = Bundle.main.url(forResource: "ageLife", withExtension: "json"),
           let raw = try? Data(contentsOf: url),
           let recorded = try? ContractExamples.decoder.decode(RecordedEvents.self, from: raw) {
            for event in recorded.events where !pool.contains(where: { $0.templateId == event.templateId }) {
                pool.append(event)
            }
        }
        return pool
    }()

    private struct RecordedEvents: Decodable {
        let events: [LifeEvent]
    }

    static let financeHomeEmpty: FinanceHome = ContractExamples.decode(#"""
    {"has_data": false, "coming_up": [], "coming_up_more": false,
     "connect_prompt": "Connect your money to see your next move"}
    """#)

    /// `Preview/Recorded/getFinanceHome.json` from `make ios-record-mock`, if recorded.
    static let recordedFinanceHome: FinanceHome? = {
        guard let url = Bundle.main.url(forResource: "getFinanceHome", withExtension: "json"),
              let raw = try? Data(contentsOf: url) else { return nil }
        return try? ContractExamples.decoder.decode(FinanceHome.self, from: raw)
    }()

    static let me: Me = ContractExamples.decode(#"""
    {"id": "usr_8f3a2c", "display_name": "Priya", "auth_provider": "apple", "created_at": "2026-10-17T12:00:00Z",
     "has_finance_data": true, "finance_inputs": ["statement"]}
    """#)

    static let importResult: ImportResult = ContractExamples.decode(#"""
    {"import_id": "imp_1", "status": "done", "provider": "monzo", "transactions": 412,
     "first_date": "2026-04-01", "last_date": "2026-10-16", "months_covered": 6.5, "warnings": [],
     "stages": [
      {"name": "read", "label": "Reading your statement", "done": true},
      {"name": "categorise", "label": "Sorting your spending", "done": true},
      {"name": "find_bills", "label": "Finding bills and subscriptions", "done": true},
      {"name": "build_profile", "label": "Building your profile", "done": true},
      {"name": "next_move", "label": "Finding your next move", "done": true}]}
    """#)

    static let manualFinance: ManualFinanceInput = ContractExamples.decode(#"""
    {"postcode": "LS6 1AN", "housing": "mortgage", "mortgage_balance": 180000.0, "mortgage_rate_pct": 4.42,
     "mortgage_years_left": 25, "deal_end": "2027-03-31", "property_value": 240000.0, "monthly_take_home": 2314.18,
     "regular_costs": [{"name": "Council tax", "monthly_amount": 191.0, "category": "bills"}], "savings": 6850.0}
    """#)

    static let samples: [SampleStatement] = (ContractExamples.decode(#"""
    {"samples": [
     {"id": "scholarship", "title": "Scholarship student",
      "description": "Scholarship and bursary, about £420 a month, no debt",
      "funding": ["scholarship", "bursary"], "months": 3, "team": false},
     {"id": "working", "title": "Working student",
      "description": "Maintenance loan and part-time pay, uses an overdraft",
      "funding": ["maintenance_loan", "part_time_job"], "months": 3, "team": false}]}
    """#) as Components.Schemas.SamplesResponse).samples

    static let habits: HabitScore = ContractExamples.decode(#"""
    {"components": {"savings_rate": 72, "months_of_cover": 40, "spend_stability": 81,
     "discretionary_share": 63, "subscription_creep": 90, "debt_pressure": 100}, "overall": 74}
    """#)

    static let reversePostcode: ReversePostcode = ContractExamples.decode(#"""
    {"postcode": "LS6 1AN", "region": "yorkshire-and-the-humber", "town": "Leeds", "status": "live"}
    """#)

    static let healthSignalStored: HealthSignalStored = ContractExamples.decode(#"""
    {"steps_per_day": 8200.0, "sleep_hours": 7.1, "measured_days": 30, "health_effect": 2,
     "updated_at": "2026-10-17T12:00:00Z"}
    """#)

    static let loggedPayment: LoggedPayment = ContractExamples.decode(#"""
    {"transaction": {"id": "tx_logged_1", "account_id": "acc_manual", "date": "2026-10-17", "amount": -4.2,
     "currency": "GBP", "description": "Pret A Manger", "merchant": "Pret A Manger"}, "category": "eating_out"}
    """#)

    static let news: NewsResponse = ContractExamples.decode(#"""
    {"status": "live", "items": [{"id": "n_1", "headline": "Lehman Brothers files for bankruptcy",
     "section": "Business", "date": "2008-09-15",
     "url": "https://www.theguardian.com/business/2008/sep/15/lehmanbrothers.creditcrunch", "source": "guardian"}]}
    """#)

    static let rateDecisions: RateDecisions = ContractExamples.decode(#"""
    {"status": "live", "next_decision": "2026-11-05", "dates": ["2026-11-05", "2026-12-17"],
     "source": {"source": "boe-mpc", "series_id": "mpc-dates", "status": "live"}}
    """#)

    /// `ChatAnswer` from the contract.
    static let chatAnswer: ChatResponse = ContractExamples.decode(#"""
    {"thread_id": "th_1", "message_id": "msg_2", "reply_to": "msg_1", "reaction": "brain",
     "bubbles": [
      {"id": "b1", "kind": "answer", "text": "Yes, for about 4 months. Your savings cover your bills and mortgage until April."},
      {"id": "b2", "kind": "caveat", "text": "This assumes your bills stay the same and you spend nothing extra."},
      {"id": "b3", "kind": "question", "text": "Do you want me to add a holiday in June?"}],
     "highlights": [{"bubble_id": "b1", "start": 17, "length": 8, "fact_id": "f_cover", "source_id": "s_you"}],
     "facts": [{"id": "f_cover", "value": 4.0, "unit": "months", "label": "Months of cover", "source_id": "s_you"}],
     "sources": [
      {"id": "s_you", "group": "your_data", "label": "Your accounts",
       "ref": {"source": "bank", "series_id": "your-accounts", "status": "live"}, "updated_at": "2026-10-17T12:00:00Z"},
      {"id": "s_boe", "group": "live_sources", "label": "Bank of England · live",
       "ref": {"source": "boe", "series_id": "IUMBEDR", "status": "live"}, "updated_at": "2026-10-17T12:00:00Z"}],
     "follow_up_question": "Do you want me to add a holiday in June?", "confidence": 0.8,
     "tool_calls": [{"name": "cash_flow_projection", "ok": true, "duration_ms": 120}],
     "verified": true, "summary_available": false, "links": [], "disclaimer": "Not financial advice"}
    """#)

    /// Out-of-scope reply (ADR 0031): fixed text, reaction `shrug`, link to the Next Move.
    static let outOfScope: ChatResponse = ContractExamples.decode(#"""
    {"thread_id": "th_1", "message_id": "msg_2", "reply_to": "msg_1", "reaction": "shrug",
     "bubbles": [{"id": "b1", "kind": "answer", "text": "I cannot help with that. I can show you your next money move."}],
     "highlights": [], "facts": [], "sources": [], "confidence": 1.0, "tool_calls": [],
     "verified": true, "summary_available": false, "links": ["next_move"], "disclaimer": "Not financial advice"}
    """#)

    static let chatThreads: ChatThreadsResponse = ContractExamples.decode(#"""
    {"threads": [{"id": "th_1", "title": "What if I lose my job?", "updated_at": "2026-10-17T12:00:00Z", "message_count": 2}]}
    """#)

    static var chatThread: ChatThread {
        ChatThread(id: "th_1", title: "What if I lose my job?", messages: [
            ChatMessage(id: "msg_1", role: .user, createdAt: now, text: "What if I lose my job?", replies: 1),
            ChatMessage(id: "msg_2", role: .penny, createdAt: now, replyTo: "msg_1", response: chatAnswer),
        ])
    }

    static let outOfScopeWords = ["stock", "shares", "bitcoin", "crypto", "lottery", "weather", "football"]

    /// The contract answer, or the out-of-scope reply for an off-topic question, with fresh ids.
    static func chatResponse(for request: ChatRequest, threadID: String, messageNumber: Int) -> ChatResponse {
        let lower = request.message.lowercased()
        var response = outOfScopeWords.contains(where: lower.contains) ? outOfScope : chatAnswer
        response.threadId = threadID
        response.replyTo = "msg_mock\(messageNumber)"
        response.messageId = "msg_mock\(messageNumber + 1)"
        return response
    }

    /// Two real-looking steps for a normal answer (account lookup, projection). None for out of scope.
    static func toolSteps(for response: ChatResponse) -> [Components.Schemas.ToolStep] {
        guard response.reaction != .shrug else { return [] }
        return [
            .init(tool: "finance_summary", label: "Checking your accounts…"),
            .init(tool: "cash_flow_projection", label: "Projecting your cash…"),
        ]
    }
}

/// Simulated Same Life room for the mock client. 3 rivals follow the caller's progress.
enum MockRoomSimulator {
    static let rivals: [(id: String, name: String, factor: Double, indexShift: Double)] = [
        ("p2", "Sam", 0.82, -4),
        ("p3", "Jo", 1.12, 6),
        ("p4", "Kai", 0.95, 1),
    ]

    static func socket(code: String, gap: Duration) -> RoomSocket {
        let (stream, continuation) = AsyncStream.makeStream(of: WsServerMessage.self)
        let state = MockRoomState(code: code)
        return RoomSocket(
            messages: stream,
            send: { message in
                for reply in await state.handle(message) {
                    if gap > .zero { try? await Task.sleep(for: gap / 2) }
                    continuation.yield(reply)
                }
                if message._type == .leave { continuation.finish() }
            },
            close: { continuation.finish() }
        )
    }
}

private actor MockRoomState {
    private var room: Room
    private var you: RoomPlayer?

    init(code: String) {
        var room = ContractExamples.room
        room.code = code
        room.mode = .group
        room.maxPlayers = 4
        room.joinUrl = "lifeline://join/\(code)"
        room.players = MockRoomSimulator.rivals.map {
            RoomPlayer(id: $0.id, name: $0.name, isHost: false, ready: true, connected: true, finished: false)
        }
        self.room = room
    }

    func handle(_ message: WsClientMessage) -> [WsServerMessage] {
        switch message._type {
        case .join:
            let player = RoomPlayer(
                id: message.playerId ?? "p1",
                name: message.name ?? you?.name ?? "You",
                isHost: true,
                ready: false,
                connected: true,
                lifeId: message.lifeId,
                finished: false
            )
            you = player
            room.players.removeAll { $0.id == player.id }
            room.players.insert(player, at: 0)
            return [.init(_type: .welcome, you: player), .init(_type: .roster, room: room)]
        case .ready:
            update { $0.ready = true }
            return [.init(_type: .roster, room: room)]
        case .start:
            room.status = .playing
            return [.init(_type: .started, room: room)]
        case .pickGame, .answer:
            // Quiz and Same Decision run in W9's MockRoomServer; this simple simulator ignores them.
            return []
        case .progress:
            update {
                $0.age = message.age
                $0.year = message.year
                $0.netWorth = message.netWorth
                $0.index = message.index
                $0.lifeId = message.lifeId ?? $0.lifeId
            }
            return MockRoomSimulator.rivals.compactMap { rival in
                guard let position = room.players.firstIndex(where: { $0.id == rival.id }) else { return nil }
                var player = room.players[position]
                player.age = message.age
                player.year = message.year
                player.netWorth = message.netWorth.map { ($0 * rival.factor).rounded() }
                player.index = message.index.map { min(100, max(0, $0 + rival.indexShift)) }
                room.players[position] = player
                return .init(_type: .rival, player: player)
            }
        case .finish:
            update { $0.finished = true }
            for index in room.players.indices { room.players[index].finished = true }
            room.status = .finished
            return [.init(_type: .finished, room: room)]
        case .leave:
            return []
        case .ping:
            return [.init(_type: .pong)]
        }
    }

    private func update(_ change: (inout RoomPlayer) -> Void) {
        guard var player = you, let position = room.players.firstIndex(where: { $0.id == player.id }) else { return }
        change(&player)
        you = player
        room.players[position] = player
    }
}
