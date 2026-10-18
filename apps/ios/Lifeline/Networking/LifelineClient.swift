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
typealias ChallengeProgress = Components.Schemas.ChallengeProgress
typealias StudentPath = Components.Schemas.StudentPath
typealias PathsResponse = Components.Schemas.PathsResponse
typealias QuickStudent = Components.Schemas.QuickStudent
typealias HabitScore = Components.Schemas.HabitScore
typealias SampleStatement = Components.Schemas.SampleStatement
typealias GameOptions = Components.Schemas.GameOptions
typealias PlayCircle = Components.Schemas.Circle
typealias CircleMember = Components.Schemas.CircleMember
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
typealias ConnectionsResponse = Components.Schemas.ConnectionsResponse
typealias ProviderConnection = Components.Schemas.ProviderConnection
typealias MonzoHistory = Components.Schemas.HistoryStatus
typealias PurchaseProduct = Components.Schemas.PurchaseVerifyRequest.ProductIdPayload
typealias PurchaseVerifyResponse = Components.Schemas.PurchaseVerifyResponse
typealias LivesResponse = Components.Schemas.LivesResponse
typealias LifeListItem = Components.Schemas.LifeListItem
// Money tab (ADR 0016, 0017)
typealias FinanceMeta = Components.Schemas.FinanceMeta
typealias FinanceOverview = Components.Schemas.FinanceOverview
typealias FinanceHome = Components.Schemas.FinanceHome
typealias SpendingResponse = Components.Schemas.SpendingResponse
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
// Forecast Next Move (ADR 0072)
typealias Forecast = Components.Schemas.Forecast
typealias ForecastSettings = Components.Schemas.ForecastSettings
typealias CategoryDetail = Components.Schemas.CategoryDetail
// Next Move (ADR 0018)
typealias NextMoveResponse = Components.Schemas.NextMoveResponse
typealias Move = Components.Schemas.Move
typealias TestMoveResult = Components.Schemas.TestMoveResult
typealias OptionOutcome = Components.Schemas.OptionOutcome
typealias PlanItem = Components.Schemas.PlanItem
typealias PlanResponse = Components.Schemas.PlanResponse
// Account and onboarding (ADR 0029, 0037)
typealias Me = Components.Schemas.Me
typealias ImportResult = Components.Schemas.ImportResult
typealias ImportStage = Components.Schemas.ImportStage
typealias ManualFinanceInput = Components.Schemas.ManualFinanceInput
typealias RegularCost = Components.Schemas.RegularCost
typealias ReversePostcode = Components.Schemas.ReversePostcode
typealias HealthSignal = Components.Schemas.HealthSignal
typealias HealthSignalStored = Components.Schemas.HealthSignalStored
typealias LogPaymentRequest = Components.Schemas.LogPaymentRequest
typealias LoggedPayment = Components.Schemas.LoggedPayment
// Ask Penny (ADR 0031)
typealias ChatRequest = Components.Schemas.ChatRequest
typealias ChatResponse = Components.Schemas.ChatResponse
typealias ChatStreamEvent = Components.Schemas.ChatStreamEvent
typealias ChatThread = Components.Schemas.ChatThread
typealias ChatThreadsResponse = Components.Schemas.ChatThreadsResponse
typealias ChatThreadSummary = Components.Schemas.ChatThreadSummary
typealias ChatContext = Components.Schemas.ChatContext
typealias ChatBubble = Components.Schemas.ChatBubble
typealias ChatMessage = Components.Schemas.ChatMessage
typealias NewsResponse = Components.Schemas.NewsResponse
typealias NewsItem = Components.Schemas.NewsItem
typealias RateDecisions = Components.Schemas.RateDecisions
// Rooms WebSocket (x-websocket on /v1/rooms/{code})
typealias WsClientMessage = Components.Schemas.WsClientMessage
typealias WsServerMessage = Components.Schemas.WsServerMessage
typealias RoomPlayer = Components.Schemas.Player

/// Every backend operation the app uses now or later. See ADR 0011.
/// `LiveClient` calls the backend. `MockClient` returns contract examples with no network.
protocol LifelineClient: Sendable {
    /// Short name for the debug menu: "live" or "mock".
    var kind: ClientKind { get }

    /// Drops cached GET responses (about 20 s per path in `LiveClient`). Call it before a pull to refresh.
    func clearResponseCache() async

    /// Disk cache for `load(_:onUpdate:)` (ADR 0060). `LiveClient` has one; `MockClient` returns nil.
    var diskCache: DiskCache? { get }

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
    /// The caller's progress on challenges (scope "you" challenges are scored on money data, not a life).
    func listChallengeProgress() async throws -> [ChallengeProgress]

    // Decision
    func createDecision(profile: DecisionProfile, lifeID: String?) async throws -> Decision
    func evaluation() async throws -> Evaluation

    // Meta
    func listSources() async throws -> [SourceStatus]

    // Money tab (ADR 0016, 0017). `month` is YYYY-MM, `date` is YYYY-MM-DD; nil means "now".
    func financeOverview() async throws -> FinanceOverview
    /// `GET /v1/finance/home`: everything Money home needs in one request. `hasData == false` is a normal state.
    func financeHome() async throws -> FinanceHome
    func financeSpending(month: String?) async throws -> SpendingResponse
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

    // Forecast (ADR 0072)
    /// `GET /v1/forecast`. `bufferPct` previews another buffer (0, 5, 10, 15, 20); nil uses the stored one.
    /// `stress` 2022 reruns with 2022 ONS inflation. Text comes in `AppLanguage.current`.
    func forecast(bufferPct: Int?, stress: Int?) async throws -> Forecast
    /// `PUT /v1/forecast/settings`: stores the buffer %.
    func setForecastSettings(bufferPct: Int) async throws -> ForecastSettings
    /// `GET /v1/finance/spending/{category}?month=`. `month` is YYYY-MM; nil means this month.
    func categoryDetail(category: String, month: String?) async throws -> CategoryDetail

    // Rooms
    func createRoom(_ request: CreateRoomRequest) async throws -> Room
    // Play with friends and Circles (ADR 0059)
    /// `GET /v1/paths`: student start paths and the premade Quick Life students (ADR 0064).
    func listPaths() async throws -> PathsResponse
    func listCircles() async throws -> [PlayCircle]
    func createCircle(name: String) async throws -> PlayCircle
    func joinCircle(code: String) async throws -> PlayCircle
    func leaveCircle(id: String) async throws
    func getRoom(code: String) async throws -> Room
    /// Opens `WS /v1/rooms/{code}?token=<jwt>`. The caller sends `join` first (with `player_id` to resume).
    /// The socket never reconnects by itself. Its `messages` stream finishes when it closes or fails.
    func roomSocket(code: String) async throws -> RoomSocket

    // Account (ADR 0029)
    func getMe() async throws -> Me
    /// `DELETE /v1/me`. Live: also clears the stored token.
    func deleteAccount() async throws
    /// `POST /v1/me/reset` (demo reset).
    func resetDemo() async throws -> Me
    /// `POST /v1/auth/logout`. Live: also clears the stored token. The next call signs in as the demo device.
    func signOut() async throws
    /// `POST /v1/auth/apple`. Live: stores the JWT (Keychain) and uses it instead of the demo token.
    func signInWithApple(identityToken: String) async throws

    // Onboarding inputs (ADR 0029)
    /// Multipart upload. `provider`: monzo, revolut, pdf or unknown; nil lets the server detect it.
    func importStatement(file: Data, fileName: String, provider: String?) async throws -> ImportResult
    /// `GET /v1/samples`: built-in sample student statements (ADR 0047).
    func listSamples() async throws -> [SampleStatement]
    /// `POST /v1/samples/{id}/import`: the data is labelled Sample data.
    func importSample(id: String) async throws -> ImportResult
    /// `GET /v1/habits`: habit score, ratios 0-100, no amounts (ADR 0052).
    func habits() async throws -> HabitScore
    func setManualFinance(_ input: ManualFinanceInput) async throws -> FinanceProfile
    func logPayment(_ request: LogPaymentRequest) async throws -> LoggedPayment
    func reversePostcode(lat: Double, lon: Double) async throws -> ReversePostcode
    func setHealthSignal(_ signal: HealthSignal) async throws -> HealthSignalStored

    // Ask Penny (ADR 0031)
    func askPenny(_ request: ChatRequest) async throws -> ChatResponse
    /// `POST /v1/chat/stream` (SSE). One element per `data:` line. The stream ends after `done`.
    /// It throws `APIError` on a transport or HTTP failure. Falling back to `askPenny` is the caller's job.
    func askPennyStream(_ request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, any Error>
    func listChatThreads() async throws -> ChatThreadsResponse
    func getChatThread(id: String) async throws -> ChatThread
    /// `from` and `to` are YYYY-MM-DD. `topic`: economy, housing, rates, jobs, energy, markets, or nil for all.
    func listNews(from: String, to: String, topic: String?) async throws -> NewsResponse
    func getRateDecisions() async throws -> RateDecisions

    // Bank
    /// `provider`: monzo (default, live) or truelayer (disabled: 409 source_disabled).
    func bankAuthLink(provider: String) async throws -> BankAuthLink
    func bankSummary(session: String) async throws -> BankSummary

    // Connected accounts: Monzo and Trading 212 (`/v1/connections`). Tokens stay on the server.
    func listConnections() async throws -> ConnectionsResponse
    /// Checked with Trading 212 first; nothing is stored when the key or secret is wrong.
    func connectTrading212(key: String, secret: String) async throws -> ProviderConnection
    /// Retries the Monzo history import. It works after the user approves access in the Monzo app.
    func syncMonzo() async throws -> MonzoHistory
    func disconnectProvider(_ provider: String) async throws -> ConnectionsResponse

    // Store (demo only)
    func verifyPurchase(product: PurchaseProduct) async throws -> PurchaseVerifyResponse
}

extension LifelineClient {
    func clearResponseCache() async {}

    // Clients without connections (tests, fixtures) answer "not available" until they implement them.
    func listConnections() async throws -> ConnectionsResponse { throw APIError.connectionsUnavailable }
    func connectTrading212(key: String, secret: String) async throws -> ProviderConnection { throw APIError.connectionsUnavailable }
    func syncMonzo() async throws -> MonzoHistory { throw APIError.connectionsUnavailable }
    func disconnectProvider(_ provider: String) async throws -> ConnectionsResponse { throw APIError.connectionsUnavailable }

    /// Paths only. Kept so older call sites with an explicit `[StudentPath]` type still compile.
    @available(*, deprecated, message: "listPaths() returns PathsResponse; use .paths and .quickStudents")
    func listPaths() async throws -> [StudentPath] {
        let response: PathsResponse = try await listPaths()
        return response.paths
    }

    var diskCache: DiskCache? { nil }

    /// Monzo consent link (the contract default provider).
    func bankAuthLink() async throws -> BankAuthLink {
        try await bankAuthLink(provider: "monzo")
    }
}

enum ClientKind: String, Sendable {
    case live
    case mock
}

extension APIError {
    /// Connections are not served by this client (fixtures, tests).
    static var connectionsUnavailable: APIError {
        .server(status: 501, code: "not_implemented", message: "This is not available in this build yet.", source: "app")
    }
}
