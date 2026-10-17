import Foundation
import OpenAPIRuntime
import OpenAPIURLSession

/// Backend client. Wraps the generated `Client` and adds demo auth and error mapping.
struct LiveClient: LifelineClient {
    let kind = ClientKind.live
    let baseURL: URL
    private let client: Client

    init(baseURL: URL, deviceID: String = DeviceIdentity.current(), session: URLSession = .shared) {
        self.baseURL = baseURL
        let transport = URLSessionTransport(configuration: .init(session: session))
        let errors = ErrorMappingMiddleware()
        let authClient = Client(serverURL: baseURL, transport: transport, middlewares: [errors])
        let tokens = DemoTokenProvider(client: authClient, deviceID: deviceID)
        self.client = Client(
            serverURL: baseURL,
            transport: transport,
            middlewares: [errors, AuthMiddleware(tokens: tokens)]
        )
    }

    /// Reads `LifelineAPIBaseURL` from Info.plist. Falls back to the contract server URL.
    static func configuredBaseURL(bundle: Bundle = .main) -> URL {
        if let raw = bundle.object(forInfoDictionaryKey: "LifelineAPIBaseURL") as? String,
           !raw.isEmpty, !raw.hasPrefix("$("),
           let url = URL(string: raw) {
            return url
        }
        return URL(string: "http://localhost:8000")!
    }

    // MARK: Lives

    func listCharacters(seed: Int?) async throws -> CharactersResponse {
        try await call { try await client.listCharacters(query: .init(seed: seed)).ok.body.json }
    }

    func createLife(_ request: CreateLifeRequest) async throws -> Life {
        try await call { try await client.createLife(body: .json(request)).created.body.json }
    }

    func getLife(id: String) async throws -> Life {
        try await call { try await client.getLife(path: .init(id: id)).ok.body.json }
    }

    func age(lifeID: String) async throws -> AgeResult {
        try await call { try await client.ageLife(path: .init(id: lifeID)).ok.body.json }
    }

    func choose(lifeID: String, eventID: String, choiceID: String) async throws -> ChoiceResult {
        try await call {
            try await client.chooseLife(
                path: .init(id: lifeID),
                body: .json(.init(eventId: eventID, choiceId: choiceID))
            ).ok.body.json
        }
    }

    func act(lifeID: String, request: ActionRequest) async throws -> ActionResult {
        try await call { try await client.actLife(path: .init(id: lifeID), body: .json(request)).ok.body.json }
    }

    func rewind(lifeID: String, decisionID: String) async throws -> RewindResult {
        try await call {
            try await client.rewindLife(path: .init(id: lifeID), body: .json(.init(decisionId: decisionID))).ok.body.json
        }
    }

    func summary(lifeID: String) async throws -> LifeSummary {
        try await call { try await client.getLifeSummary(path: .init(id: lifeID)).ok.body.json }
    }

    func listLives() async throws -> LivesResponse {
        try await call { try await client.listLives().ok.body.json }
    }

    // MARK: Money tab

    func financeOverview() async throws -> FinanceOverview {
        try await call { try await client.getFinanceOverview().ok.body.json }
    }

    func financeSpending(month: String?) async throws -> SpendingResponse {
        try await call { try await client.getFinanceSpending(query: .init(month: month)).ok.body.json }
    }

    func insights(months: Int) async throws -> SpendingInsights {
        try await call { try await client.getFinanceInsights(query: .init(months: months)).ok.body.json }
    }

    func subscriptions() async throws -> SubscriptionsResponse {
        try await call { try await client.listSubscriptions().ok.body.json }
    }

    func bills() async throws -> BillsResponse {
        try await call { try await client.listBills().ok.body.json }
    }

    func budgets(month: String?) async throws -> BudgetsResponse {
        try await call { try await client.listBudgets(query: .init(month: month)).ok.body.json }
    }

    func updateBudgets(_ limits: [BudgetLimit]) async throws -> BudgetsResponse {
        try await call { try await client.updateBudgets(body: .json(.init(items: limits))).ok.body.json }
    }

    func goals() async throws -> GoalsResponse {
        try await call { try await client.listGoals().ok.body.json }
    }

    func createGoal(_ request: CreateGoalRequest) async throws -> SavingsGoal {
        try await call { try await client.createGoal(body: .json(request)).created.body.json }
    }

    func financeProfile() async throws -> FinanceProfile {
        try await call { try await client.getFinanceProfile().ok.body.json }
    }

    func spendPrediction(date: String?) async throws -> SpendPrediction {
        try await call { try await client.getSpendPrediction(query: .init(date: date)).ok.body.json }
    }

    func guesses() async throws -> GuessesResponse {
        try await call { try await client.listGuesses().ok.body.json }
    }

    func makeGuess(date: String, amount: Double) async throws -> SpendPrediction {
        try await call { try await client.makeGuess(body: .json(.init(date: date, amount: amount))).created.body.json }
    }

    func predictionEvaluation() async throws -> PredictionEvaluation {
        try await call { try await client.getPredictionEvaluation().ok.body.json }
    }

    // MARK: Next Move

    func nextMove() async throws -> NextMoveResponse {
        try await call { try await client.getNextMove().ok.body.json }
    }

    func testNextMove(moveID: String, optionIDs: [String]?) async throws -> TestMoveResult {
        try await call {
            try await client.testNextMove(body: .json(.init(moveId: moveID, optionIds: optionIDs))).ok.body.json
        }
    }

    func plan() async throws -> PlanResponse {
        try await call { try await client.getPlan().ok.body.json }
    }

    func addPlanItem(moveID: String) async throws -> PlanItem {
        try await call { try await client.addPlanItem(body: .json(.init(moveId: moveID))).created.body.json }
    }

    // MARK: Learn

    func listConcepts() async throws -> [Concept] {
        try await call { try await client.listConcepts().ok.body.json.concepts }
    }

    func listChallenges() async throws -> [Challenge] {
        try await call { try await client.listChallenges().ok.body.json.challenges }
    }

    // MARK: Decision

    func createDecision(profile: DecisionProfile, lifeID: String?) async throws -> Decision {
        try await call {
            try await client.createDecision(body: .json(.init(profile: profile, lifeId: lifeID))).ok.body.json
        }
    }

    func evaluation() async throws -> Evaluation {
        try await call { try await client.getEvaluation().ok.body.json }
    }

    // MARK: Meta

    func listSources() async throws -> [SourceStatus] {
        try await call { try await client.listSources().ok.body.json.sources }
    }

    // MARK: Rooms

    func createRoom(_ request: CreateRoomRequest) async throws -> Room {
        try await call { try await client.createRoom(body: .json(request)).created.body.json }
    }

    func getRoom(code: String) async throws -> Room {
        try await call { try await client.getRoom(path: .init(code: code)).ok.body.json }
    }

    // MARK: Connections

    func listConnections() async throws -> ConnectionsResponse {
        try await call { try await client.listConnections().ok.body.json }
    }

    func connectTrading212(apiKey: String, apiSecret: String) async throws -> ProviderConnection {
        try await call {
            try await client.connectTrading212(body: .json(.init(apiKey: apiKey, apiSecret: apiSecret))).ok.body.json
        }
    }

    func connectMonzoToken(_ accessToken: String) async throws -> ProviderConnection {
        try await call { try await client.connectMonzoToken(body: .json(.init(accessToken: accessToken))).ok.body.json }
    }

    func syncMonzo() async throws -> HistoryStatus {
        try await call { try await client.syncMonzo().ok.body.json }
    }

    func disconnect(_ provider: ProviderID) async throws -> ConnectionsResponse {
        guard let payload = Operations.DisconnectProvider.Input.Path.ProviderPayload(rawValue: provider.rawValue) else {
            throw APIError.unexpected(status: 0)
        }
        return try await call { try await client.disconnectProvider(path: .init(provider: payload)).ok.body.json }
    }

    // MARK: Investing and habits

    func investments() async throws -> InvestmentsResponse {
        try await call { try await client.getInvestments().ok.body.json }
    }

    func habits() async throws -> HabitFactors {
        try await call { try await client.getHabits().ok.body.json }
    }

    func isaPeriods() async throws -> IsaPeriodsResponse {
        try await call { try await client.getIsaPeriods().ok.body.json }
    }

    func isaBacktest(_ query: IsaBacktestQuery) async throws -> IsaBacktestResponse {
        try await call { try await client.postIsaBacktest(body: .json(query)).ok.body.json }
    }

    func isaScenarios(_ query: IsaScenariosQuery) async throws -> IsaScenariosResult {
        try await call { try await client.postIsaScenarios(body: .json(query)).ok.body.json }
    }

    // MARK: Friends

    func leaderboard() async throws -> Leaderboard {
        try await call { try await client.getLeaderboard().ok.body.json }
    }

    func createFriendInvite(rotate: Bool) async throws -> InviteCode {
        try await call { try await client.createFriendInvite(query: .init(rotate: rotate)).ok.body.json }
    }

    func joinFriend(code: String) async throws -> Leaderboard {
        try await call { try await client.joinFriend(body: .json(.init(code: code))).ok.body.json }
    }

    func myFriendCard() async throws -> FriendCard {
        try await call { try await client.getMyFriendCard().ok.body.json }
    }

    func updateMyFriendCard(_ settings: ShareSettings) async throws -> FriendCard {
        try await call { try await client.updateMyFriendCard(body: .json(settings)).ok.body.json }
    }

    func removeFriend(id: String) async throws -> Leaderboard {
        try await call { try await client.removeFriend(path: .init(friendId: id)).ok.body.json }
    }

    // MARK: Bank

    func bankAuthLink() async throws -> BankAuthLink {
        try await call { try await client.getBankAuthLink().ok.body.json }
    }

    func bankSummary(session: String) async throws -> BankSummary {
        try await call { try await client.getBankSummary(query: .init(session: session)).ok.body.json }
    }

    // MARK: Store

    func verifyPurchase(product: PurchaseProduct) async throws -> PurchaseVerifyResponse {
        try await call {
            try await client.verifyPurchase(body: .json(.init(productId: product, demo: true))).ok.body.json
        }
    }

    /// Runs one operation and maps every failure to `APIError`.
    /// The generated `.ok` accessors throw on an undocumented case; that becomes `.unexpected`.
    private func call<T: Sendable>(_ body: @Sendable () async throws -> T) async throws -> T {
        do {
            return try await body()
        } catch {
            throw APIError.map(error)
        }
    }
}

/// Gets a JWT from `POST /v1/auth/demo` and caches it in memory.
actor DemoTokenProvider: TokenProviding {
    private let client: Client
    private let deviceID: String
    private var cached: String?
    private var inFlight: Task<String, any Error>?

    init(client: Client, deviceID: String) {
        self.client = client
        self.deviceID = deviceID
    }

    func token() async throws -> String {
        if let cached { return cached }
        if let inFlight { return try await inFlight.value }
        let client = self.client
        let deviceID = self.deviceID
        let task = Task<String, any Error> {
            try await client.signInDemo(body: .json(.init(deviceId: deviceID))).ok.body.json.accessToken
        }
        inFlight = task
        defer { inFlight = nil }
        let value = try await task.value
        cached = value
        return value
    }

    func invalidate() {
        cached = nil
    }
}

/// Anonymous device id for demo sign-in. Stored in UserDefaults; it is not a secret.
///
/// Order of precedence:
/// 1. Launch argument `-demoDeviceID <id>` (for example `demo-presenter-01` from `make demo-seed`).
/// 2. Debug builds only: UserDefaults `debug.demoDeviceID` (set from the hidden debug menu).
/// 3. The stored random id (`lifeline.deviceID`), created on first launch.
enum DeviceIdentity {
    static let defaultsKey = "lifeline.deviceID"
    static let debugOverrideKey = "debug.demoDeviceID"
    static let launchArgument = "-demoDeviceID"

    static func current(
        arguments: [String] = ProcessInfo.processInfo.arguments,
        defaults: UserDefaults = .standard,
        isDebugBuild: Bool = ClientFactory.isDebugBuild
    ) -> String {
        if let fromArgument = launchOverride(arguments), isValid(fromArgument) {
            return fromArgument
        }
        if isDebugBuild, let debug = defaults.string(forKey: debugOverrideKey), isValid(debug) {
            return debug
        }
        if let existing = defaults.string(forKey: defaultsKey), isValid(existing) {
            return existing
        }
        let created = UUID().uuidString
        defaults.set(created, forKey: defaultsKey)
        return created
    }

    /// The value after `-demoDeviceID`, if present.
    static func launchOverride(_ arguments: [String]) -> String? {
        guard let position = arguments.firstIndex(of: launchArgument), arguments.indices.contains(position + 1) else {
            return nil
        }
        return arguments[position + 1]
    }

    /// Matches the contract: `^[A-Za-z0-9-]+$`, 8 to 64 characters.
    static func isValid(_ id: String) -> Bool {
        (8...64).contains(id.count) && id.allSatisfy { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == "-") }
    }
}
