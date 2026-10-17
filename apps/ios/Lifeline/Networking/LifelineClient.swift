import Foundation

// Short names for the generated contract types. The generated code is the single source of truth.
// Only ViewModels, the client layer and tests use these. Views never do (ADR 0011).
typealias Life = Components.Schemas.Life
typealias LifeEvent = Components.Schemas.Event
typealias EventChoice = Components.Schemas.Choice
typealias CharacterSpec = Components.Schemas.CharacterSpec
typealias CharactersResponse = Components.Schemas.CharactersResponse
typealias CreateLifeRequest = Components.Schemas.CreateLifeRequest
typealias AgeResult = Components.Schemas.AgeResult
typealias ChoiceResult = Components.Schemas.ChoiceResult
typealias ActionRequest = Components.Schemas.ActionRequest
typealias ActionResult = Components.Schemas.ActionResult
typealias RewindResult = Components.Schemas.RewindResult
typealias LifeSummary = Components.Schemas.LifeSummary
typealias Outcome = Components.Schemas.Outcome
typealias Lesson = Components.Schemas.Lesson
typealias Concept = Components.Schemas.Concept
typealias Challenge = Components.Schemas.Challenge
typealias SourceRef = Components.Schemas.SourceRef
typealias SourceStatus = Components.Schemas.SourceStatus
typealias YearLog = Components.Schemas.YearLog
typealias Decision = Components.Schemas.Decision
typealias DecisionProfile = Components.Schemas.DecisionProfile
typealias Evaluation = Components.Schemas.Evaluation
typealias Room = Components.Schemas.Room
typealias CreateRoomRequest = Components.Schemas.CreateRoomRequest
typealias BankAuthLink = Components.Schemas.BankAuthLink
typealias BankSummary = Components.Schemas.BankSummary
typealias PurchaseProduct = Components.Schemas.PurchaseVerifyRequest.ProductIdPayload
typealias PurchaseVerifyResponse = Components.Schemas.PurchaseVerifyResponse
typealias LivesResponse = Components.Schemas.LivesResponse
typealias LifeListItem = Components.Schemas.LifeListItem
// Money tab (ADR 0016, 0017)
typealias FinanceMeta = Components.Schemas.FinanceMeta
typealias FinanceOverview = Components.Schemas.FinanceOverview
typealias SpendingResponse = Components.Schemas.SpendingResponse
typealias SpendingInsights = Components.Schemas.SpendingInsights
typealias SubscriptionsResponse = Components.Schemas.SubscriptionsResponse
typealias BillsResponse = Components.Schemas.BillsResponse
typealias BudgetsResponse = Components.Schemas.BudgetsResponse
typealias BudgetLimit = Components.Schemas.BudgetLimit
typealias GoalsResponse = Components.Schemas.GoalsResponse
typealias SavingsGoal = Components.Schemas.SavingsGoal
typealias CreateGoalRequest = Components.Schemas.CreateGoalRequest
typealias FinanceProfile = Components.Schemas.FinanceProfile
typealias PersonalFact = Components.Schemas.PersonalFact
typealias SpendPrediction = Components.Schemas.SpendPrediction
typealias GuessesResponse = Components.Schemas.GuessesResponse
typealias PredictionEvaluation = Components.Schemas.PredictionEvaluation
// Next Move (ADR 0018)
typealias NextMoveResponse = Components.Schemas.NextMoveResponse
typealias Move = Components.Schemas.Move
typealias TestMoveResult = Components.Schemas.TestMoveResult
typealias OptionOutcome = Components.Schemas.OptionOutcome
typealias PlanItem = Components.Schemas.PlanItem
typealias PlanResponse = Components.Schemas.PlanResponse

// Connections, investing and habits
typealias ConnectionsResponse = Components.Schemas.ConnectionsResponse
typealias ProviderConnection = Components.Schemas.ProviderConnection
typealias HistoryStatus = Components.Schemas.HistoryStatus
typealias InvestmentsResponse = Components.Schemas.InvestmentsResponse
typealias Holding = Components.Schemas.Holding
typealias HabitFactors = Components.Schemas.HabitFactors
typealias HabitFactor = Components.Schemas.HabitFactor
typealias IsaPeriodsResponse = Components.Schemas.IsaPeriodsResponse
typealias IsaStrategy = Components.Schemas.IsaStrategy
typealias IsaPeriod = Components.Schemas.IsaPeriod
typealias IsaBacktestMetrics = Components.Schemas.IsaBacktestMetrics
typealias ScenarioPath = Components.Schemas.ScenarioPath
typealias ScenarioFan = Components.Schemas.ScenarioFan
typealias HabitWindow = Components.Schemas.HabitWindow
typealias IsaBacktestQuery = Components.Schemas.IsaBacktestQuery
typealias IsaBacktestResponse = Components.Schemas.IsaBacktestResponse
typealias IsaBacktestResult = Components.Schemas.IsaBacktestResult
typealias IsaScenariosQuery = Components.Schemas.IsaScenariosQuery
typealias IsaScenariosResult = Components.Schemas.IsaScenariosResult
// Friends
typealias Leaderboard = Components.Schemas.Leaderboard
typealias LeaderboardEntry = Components.Schemas.LeaderboardEntry
typealias FriendCard = Components.Schemas.FriendCard
typealias InviteCode = Components.Schemas.InviteCode
typealias ShareSettings = Components.Schemas.ShareSettings

/// Providers the app can connect. Raw values match the contract path parameter.
enum ProviderID: String, Sendable, CaseIterable, Hashable {
    case monzo
    case trading212

    var displayName: String {
        switch self {
        case .monzo: "Monzo"
        case .trading212: "Trading212"
        }
    }
}

/// Every backend operation the app uses now or later. See ADR 0011.
/// `LiveClient` calls the backend. `MockClient` returns contract examples with no network.
protocol LifelineClient: Sendable {
    /// Short name for the debug menu: "live" or "mock".
    var kind: ClientKind { get }

    // Lives
    func listCharacters(seed: Int?) async throws -> CharactersResponse
    func createLife(_ request: CreateLifeRequest) async throws -> Life
    func getLife(id: String) async throws -> Life
    func age(lifeID: String) async throws -> AgeResult
    func choose(lifeID: String, eventID: String, choiceID: String) async throws -> ChoiceResult
    func act(lifeID: String, request: ActionRequest) async throws -> ActionResult
    func rewind(lifeID: String, decisionID: String) async throws -> RewindResult
    func summary(lifeID: String) async throws -> LifeSummary
    func listLives() async throws -> LivesResponse

    // Learn
    func listConcepts() async throws -> [Concept]
    func listChallenges() async throws -> [Challenge]

    // Decision
    func createDecision(profile: DecisionProfile, lifeID: String?) async throws -> Decision
    func evaluation() async throws -> Evaluation

    // Meta
    func listSources() async throws -> [SourceStatus]

    // Money tab (ADR 0016, 0017). `month` is YYYY-MM, `date` is YYYY-MM-DD; nil means "now".
    func financeOverview() async throws -> FinanceOverview
    func financeSpending(month: String?) async throws -> SpendingResponse
    /// Spending insights over the last `months` complete months (1 to 12). Fewer are used when history is short.
    func insights(months: Int) async throws -> SpendingInsights
    func subscriptions() async throws -> SubscriptionsResponse
    func bills() async throws -> BillsResponse
    func budgets(month: String?) async throws -> BudgetsResponse
    func updateBudgets(_ limits: [BudgetLimit]) async throws -> BudgetsResponse
    func goals() async throws -> GoalsResponse
    func createGoal(_ request: CreateGoalRequest) async throws -> SavingsGoal
    func financeProfile() async throws -> FinanceProfile
    func spendPrediction(date: String?) async throws -> SpendPrediction
    func guesses() async throws -> GuessesResponse
    func makeGuess(date: String, amount: Double) async throws -> SpendPrediction
    func predictionEvaluation() async throws -> PredictionEvaluation

    // Next Move (ADR 0018)
    func nextMove() async throws -> NextMoveResponse
    func testNextMove(moveID: String, optionIDs: [String]?) async throws -> TestMoveResult
    func plan() async throws -> PlanResponse
    func addPlanItem(moveID: String) async throws -> PlanItem

    // Connections (Monzo, Trading212). Keys are sent once and never stored on the device.
    func listConnections() async throws -> ConnectionsResponse
    func connectTrading212(apiKey: String, apiSecret: String) async throws -> ProviderConnection
    func connectMonzoToken(_ accessToken: String) async throws -> ProviderConnection
    func syncMonzo() async throws -> HistoryStatus
    func disconnect(_ provider: ProviderID) async throws -> ConnectionsResponse

    // Investing and habits
    func investments() async throws -> InvestmentsResponse
    func habits() async throws -> HabitFactors
    func isaPeriods() async throws -> IsaPeriodsResponse
    func isaBacktest(_ query: IsaBacktestQuery) async throws -> IsaBacktestResponse
    func isaScenarios(_ query: IsaScenariosQuery) async throws -> IsaScenariosResult

    // Friends: scores and percentages only, never amounts
    func leaderboard() async throws -> Leaderboard
    func createFriendInvite(rotate: Bool) async throws -> InviteCode
    func joinFriend(code: String) async throws -> Leaderboard
    func myFriendCard() async throws -> FriendCard
    func updateMyFriendCard(_ settings: ShareSettings) async throws -> FriendCard
    func removeFriend(id: String) async throws -> Leaderboard

    // Rooms
    func createRoom(_ request: CreateRoomRequest) async throws -> Room
    func getRoom(code: String) async throws -> Room

    // Bank
    func bankAuthLink() async throws -> BankAuthLink
    func bankSummary(session: String) async throws -> BankSummary

    // Store (demo only)
    func verifyPurchase(product: PurchaseProduct) async throws -> PurchaseVerifyResponse
}

enum ClientKind: String, Sendable {
    case live
    case mock
}
