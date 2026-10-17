import Foundation

/// In-memory client built from the contract examples (ADR 0011).
/// Returns at once and never calls the network. It simulates AGE, choices, actions and rewind
/// well enough for the UI test flow and the Playground.
///
/// Every number it returns comes from the contract examples or from the example deltas.
actor MockClient: LifelineClient {
    nonisolated let kind = ClientKind.mock
    private var lives: [String: Life] = [:]
    private var nextLifeNumber = 1
    private var nextRoomPlayer = 2
    private var budgetLimits: [String: Double] = [:]
    private var createdGoals: [SavingsGoal] = []
    /// Guesses made in this session, by date (YYYY-MM-DD). One per day (ADR 0017).
    private var guessesByDate: [String: Double] = [:]
    private var planItems: [PlanItem] = []
    private var friends: [FriendCard] = SampleFriends.initialFriends
    private var myName = "You"
    private var shareMix = false
    private var inviteCode = SampleFriends.myCode
    private let friendsOffline: Bool
    private var monzo: ProviderConnection?
    private var trading212: ProviderConnection?
    /// Monzo refuses the history import until the user approves in the app. This many syncs fail first.
    private var monzoSyncsBeforeApproval: Int
    private(set) var syncCalls = 0
    private let data: MockData

    /// - Parameter data: `.contract` (default: tests, previews, Playground) or `.recorded` (the app's mock mode).
    init(data: MockData = .contract, monzoSyncsBeforeApproval: Int = 0, friendsOffline: Bool = false) {
        self.friendsOffline = friendsOffline
        self.data = data
        self.monzoSyncsBeforeApproval = monzoSyncsBeforeApproval
    }

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
        var event = ContractExamples.event
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
    func financeSpending(month: String?) async throws -> SpendingResponse { data.spending }
    func insights(months: Int) async throws -> SpendingInsights { SampleInsights.make(months: months) }
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
        room.mode = Room.ModePayload(rawValue: request.mode.rawValue) ?? .duel
        room.presetId = request.presetId
        room.startYear = request.startYear
        room.players = [.init(id: "p1", name: request.hostName, isHost: true, finished: false)]
        return room
    }

    func getRoom(code: String) async throws -> Room {
        var room = ContractExamples.room
        room.code = code
        return room
    }

    // MARK: Connections (sample data, labelled mock)

    func listConnections() async throws -> ConnectionsResponse {
        SampleInvesting.connections(monzo: monzo, trading212: trading212)
    }

    func connectTrading212(apiKey: String, apiSecret: String) async throws -> ProviderConnection {
        guard !apiKey.isEmpty, !apiSecret.isEmpty, apiKey != "invalid" else {
            throw APIError.server(status: 400, code: "provider_auth", message: "Trading212 did not accept those details. Check them and try again.", source: "trading212")
        }
        var connection = SampleInvesting.trading212Connected
        connection.dataStatus = .mock
        connection.hint = "…" + String(apiKey.suffix(4))
        trading212 = connection
        return connection
    }

    func connectMonzoToken(_ accessToken: String) async throws -> ProviderConnection {
        var connection = monzoSyncsBeforeApproval > 0 ? SampleInvesting.monzoWaitingForApproval : SampleInvesting.monzoConnected
        connection.dataStatus = .mock
        monzo = connection
        return connection
    }

    func syncMonzo() async throws -> HistoryStatus {
        guard monzo != nil else {
            throw APIError.server(status: 409, code: "not_connected", message: "Monzo is not connected.", source: "monzo")
        }
        syncCalls += 1
        if syncCalls <= monzoSyncsBeforeApproval {
            return HistoryStatus(synced: false, count: 0, lastError: "auth")
        }
        monzo?.history = SampleInvesting.monzoConnected.history
        return SampleInvesting.monzoConnected.history!
    }

    func disconnect(_ provider: ProviderID) async throws -> ConnectionsResponse {
        switch provider {
        case .monzo: monzo = nil
        case .trading212: trading212 = nil
        }
        return SampleInvesting.connections(monzo: monzo, trading212: trading212)
    }

    // MARK: Investing and habits (sample data, labelled mock)

    func investments() async throws -> InvestmentsResponse { SampleInvesting.investments }
    func habits() async throws -> HabitFactors { SampleInvesting.habits }
    func isaPeriods() async throws -> IsaPeriodsResponse { SampleInvesting.periods }
    func isaBacktest(_ query: IsaBacktestQuery) async throws -> IsaBacktestResponse { SampleInvesting.backtest(query) }
    func isaScenarios(_ query: IsaScenariosQuery) async throws -> IsaScenariosResult { SampleInvesting.scenarios(query) }

    // MARK: Friends (sample data, labelled mock)

    func leaderboard() async throws -> Leaderboard {
        if friendsOffline { throw APIError.network }
        return SampleFriends.leaderboard(me: SampleFriends.me(name: myName, shareMix: shareMix), friends: friends, code: inviteCode)
    }

    func createFriendInvite(rotate: Bool) async throws -> InviteCode {
        if rotate { inviteCode = Self.rotatedCode(after: inviteCode) }
        return InviteCode(code: inviteCode)
    }

    func joinFriend(code: String) async throws -> Leaderboard {
        let clean = code.uppercased().filter { !$0.isWhitespace }
        if clean == inviteCode {
            throw APIError.server(status: 400, code: "cannot_add_self", message: "That is your own code.", source: "friends")
        }
        guard let card = SampleFriends.joinable[clean] else {
            throw APIError.server(status: 404, code: "invite_not_found", message: "No one has that code.", source: "friends")
        }
        if !friends.contains(where: { $0.friendId == card.friendId }) { friends.append(card) }
        return try await leaderboard()
    }

    func myFriendCard() async throws -> FriendCard {
        if friendsOffline { throw APIError.network }
        return SampleFriends.me(name: myName, shareMix: shareMix)
    }

    func updateMyFriendCard(_ settings: ShareSettings) async throws -> FriendCard {
        myName = settings.displayName
        shareMix = settings.shareMix
        return SampleFriends.me(name: myName, shareMix: shareMix)
    }

    func removeFriend(id: String) async throws -> Leaderboard {
        friends.removeAll { $0.friendId == id }
        return try await leaderboard()
    }

    private static func rotatedCode(after code: String) -> String {
        code == "H3C9TD4V" ? SampleFriends.myCode : "H3C9TD4V"
    }

    // MARK: Bank

    func bankAuthLink() async throws -> BankAuthLink { ContractExamples.bankAuthLink }
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
