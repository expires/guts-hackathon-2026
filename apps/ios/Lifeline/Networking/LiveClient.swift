import Foundation
import OpenAPIRuntime
import OpenAPIURLSession

/// Backend client. Wraps the generated `Client` and adds demo auth and error mapping.
struct LiveClient: LifelineClient {
    let kind = ClientKind.live
    let baseURL: URL
    private let client: Client
    private let tokens: DemoTokenProvider
    private let session: URLSession
    private let cache: ResponseCache
    let diskCache: DiskCache?

    init(
        baseURL: URL,
        deviceID: String = DeviceIdentity.current(),
        session: URLSession = .shared,
        tokenStore: TokenStore = .standard,
        diskCache: DiskCache? = .standard
    ) {
        self.baseURL = baseURL
        self.diskCache = diskCache
        self.session = session
        let transport = URLSessionTransport(configuration: .init(session: session))
        let errors = ErrorMappingMiddleware()
        let configuration = Configuration(dateTranscoder: FlexibleISO8601Transcoder())
        let authClient = Client(serverURL: baseURL, configuration: configuration, transport: transport, middlewares: [errors])
        let tokens = DemoTokenProvider(client: authClient, deviceID: deviceID, store: tokenStore)
        self.tokens = tokens
        let cache = ResponseCache()
        self.cache = cache
        // Outermost first: GET cache and de-duplication, error mapping, quiet 429 retry, auth (401 retry).
        self.client = Client(
            serverURL: baseURL,
            configuration: configuration,
            transport: transport,
            middlewares: [ResponseCacheMiddleware(cache: cache), errors, RateLimitRetryMiddleware(), AuthMiddleware(tokens: tokens)]
        )
    }

    func clearResponseCache() async {
        await cache.clear()
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

    func financeHome() async throws -> FinanceHome {
        try await call { try await client.getFinanceHome().ok.body.json }
    }

    func financeSpending(month: String?) async throws -> SpendingResponse {
        try await call { try await client.getFinanceSpending(query: .init(month: month)).ok.body.json }
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
        // Move text in the app language (ADR 0069); numbers are the same in every language.
        let language = Operations.GetNextMove.Input.Query.LanguagePayload(rawValue: AppLanguage.current.rawValue)
        return try await call { try await client.getNextMove(query: .init(language: language)).ok.body.json }
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

    func listChallengeProgress() async throws -> [ChallengeProgress] {
        try await call { try await client.listChallenges().ok.body.json.progress ?? [] }
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

    func listSamples() async throws -> [SampleStatement] {
        try await call { try await client.listSamples().ok.body.json.samples }
    }

    func importSample(id: String) async throws -> ImportResult {
        try await call { try await client.importSample(path: .init(sampleId: id)).created.body.json }
    }

    func habits() async throws -> HabitScore {
        try await call { try await client.getHabits().ok.body.json }
    }

    func listPaths() async throws -> PathsResponse {
        try await call { try await client.listPaths().ok.body.json }
    }

    func listCircles() async throws -> [PlayCircle] {
        try await call { try await client.listCircles().ok.body.json.circles }
    }

    func createCircle(name: String) async throws -> PlayCircle {
        try await call { try await client.createCircle(body: .json(.init(name: name))).created.body.json }
    }

    func joinCircle(code: String) async throws -> PlayCircle {
        try await call { try await client.joinCircle(body: .json(.init(code: code))).ok.body.json }
    }

    func leaveCircle(id: String) async throws {
        _ = try await call { try await client.leaveCircle(path: .init(circleId: id)).noContent }
    }

    func getRoom(code: String) async throws -> Room {
        try await call { try await client.getRoom(path: .init(code: code)).ok.body.json }
    }

    func roomSocket(code: String) async throws -> RoomSocket {
        let token = try await call { try await tokens.token() }
        guard let url = RoomSocket.url(baseURL: baseURL, code: code, token: token) else {
            throw APIError.unexpected(status: 0)
        }
        return RoomSocket.live(url: url, session: session)
    }

    // MARK: Account

    func getMe() async throws -> Me {
        try await call { try await client.getMe().ok.body.json }
    }

    func deleteAccount() async throws {
        _ = try await call { try await client.deleteAccount().noContent }
        await tokens.clear()
        await forgetUserData()
    }

    func resetDemo() async throws -> Me {
        let me = try await call { try await client.resetDemo().ok.body.json }
        await forgetUserData()
        return me
    }

    /// Sign-out, reset, delete: drop the memory and disk caches of the user's data.
    private func forgetUserData() async {
        await cache.clear()
        await diskCache?.clearUser()
    }

    func signOut() async throws {
        // The local token goes even when the server call fails.
        do {
            _ = try await call { try await client.signOut().noContent }
        } catch {
            await tokens.clear()
            await forgetUserData()
            throw error
        }
        await tokens.clear()
        await forgetUserData()
    }

    func signInWithApple(identityToken: String) async throws {
        let token = try await call {
            try await client.signInWithApple(body: .json(.init(identityToken: identityToken))).ok.body.json.accessToken
        }
        await tokens.useAppleToken(token)
    }

    // MARK: Onboarding inputs

    func importStatement(file: Data, fileName: String, provider: String?) async throws -> ImportResult {
        try await call {
            var parts: [Operations.ImportStatement.Input.Body.MultipartFormPayload] = [
                .file(.init(payload: .init(body: HTTPBody(file)), filename: fileName)),
            ]
            if let provider {
                parts.append(.provider(.init(payload: .init(body: HTTPBody(provider)))))
            }
            return try await client.importStatement(body: .multipartForm(.init(parts))).created.body.json
        }
    }

    func setManualFinance(_ input: ManualFinanceInput) async throws -> FinanceProfile {
        try await call { try await client.setManualFinance(body: .json(input)).ok.body.json }
    }

    func logPayment(_ request: LogPaymentRequest) async throws -> LoggedPayment {
        try await call { try await client.logPayment(body: .json(request)).created.body.json }
    }

    func reversePostcode(lat: Double, lon: Double) async throws -> ReversePostcode {
        try await call { try await client.reversePostcode(query: .init(lat: lat, lon: lon)).ok.body.json }
    }

    func setHealthSignal(_ signal: HealthSignal) async throws -> HealthSignalStored {
        try await call { try await client.setHealthSignal(body: .json(signal)).ok.body.json }
    }

    // MARK: Ask Penny

    func askPenny(_ request: ChatRequest) async throws -> ChatResponse {
        let request = Self.withLanguage(request)
        return try await call { try await client.askPenny(body: .json(request)).ok.body.json }
    }

    /// Penny answers in the app language (ADR 0063) unless the caller set `language`.
    static func withLanguage(_ request: ChatRequest, language: AppLanguage = .current) -> ChatRequest {
        guard request.language == nil else { return request }
        var request = request
        request.language = .init(rawValue: language.rawValue)
        return request
    }

    func askPennyStream(_ request: ChatRequest) -> AsyncThrowingStream<ChatStreamEvent, any Error> {
        let client = self.client
        let request = Self.withLanguage(request)
        return AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    let body = try await client.askPennyStream(body: .json(request)).ok.body.textEventStream
                    for try await event in ChatStream.events(from: body) {
                        continuation.yield(event)
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: APIError.map(error))
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    func listChatThreads() async throws -> ChatThreadsResponse {
        try await call { try await client.listChatThreads().ok.body.json }
    }

    func getChatThread(id: String) async throws -> ChatThread {
        try await call { try await client.getChatThread(path: .init(id: id)).ok.body.json }
    }

    func listNews(from: String, to: String, topic: String?) async throws -> NewsResponse {
        try await call {
            try await client.listNews(
                query: .init(from: from, to: to, topic: topic.flatMap { .init(rawValue: $0) })
            ).ok.body.json
        }
    }

    func getRateDecisions() async throws -> RateDecisions {
        try await call { try await client.getRateDecisions().ok.body.json }
    }

    // MARK: Bank

    func bankAuthLink(provider: String) async throws -> BankAuthLink {
        try await call {
            try await client.getBankAuthLink(query: .init(provider: .init(rawValue: provider))).ok.body.json
        }
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

/// Supplies the session JWT.
/// - After Sign in with Apple: the Apple session token from the Keychain.
/// - Otherwise: a demo token from `POST /v1/auth/demo`, cached in memory.
/// A rejected Apple token (401) is dropped, and the app falls back to demo sign-in.
actor DemoTokenProvider: TokenProviding {
    private let client: Client
    private let deviceID: String
    private let store: TokenStore
    private var cached: String?
    private var appleToken: String?
    private var inFlight: Task<String, any Error>?

    init(client: Client, deviceID: String, store: TokenStore = .standard) {
        self.client = client
        self.deviceID = deviceID
        self.store = store
        self.appleToken = store.read()
    }

    func token() async throws -> String {
        if let appleToken { return appleToken }
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
        if appleToken != nil {
            appleToken = nil
            store.delete()
        }
        cached = nil
    }

    /// Stores the Apple session token and uses it for every later call.
    func useAppleToken(_ token: String) {
        appleToken = token
        store.write(token)
        cached = nil
    }

    /// Sign-out and account deletion: forget every token.
    func clear() {
        appleToken = nil
        cached = nil
        store.delete()
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

// MARK: Learn (ADR 0068)
extension LiveClient: LearnService {
    func learnPath(language: AppLanguage) async throws -> LearnWire.Path {
        try await call { try await client.getLearnPath(query: .init(language: .init(rawValue: language.rawValue))).ok.body.json }
    }

    func learnLesson(id: String, language: AppLanguage) async throws -> LearnWire.Lesson {
        try await call {
            try await client.getLearnLesson(path: .init(lessonId: id), query: .init(language: .init(rawValue: language.rawValue))).ok.body.json
        }
    }

    func attemptLearnLesson(id: String, answers: [String: String], language: AppLanguage) async throws -> LearnWire.AttemptResult {
        try await call {
            try await client.attemptLearnLesson(
                path: .init(lessonId: id),
                query: .init(language: .init(rawValue: language.rawValue)),
                body: .json(.init(answers: .init(additionalProperties: answers)))
            ).ok.body.json
        }
    }
}

// MARK: Forecast (ADR 0072)
extension LiveClient {
    func forecast(bufferPct: Int?, stress: Int?) async throws -> Forecast {
        // Text in the app language; numbers are the same in every language.
        let query = Operations.GetForecast.Input.Query(
            bufferPct: bufferPct.flatMap { .init(rawValue: $0) },
            stress: stress.flatMap { .init(rawValue: $0) },
            language: .init(rawValue: AppLanguage.current.rawValue)
        )
        return try await call { try await client.getForecast(query: query).ok.body.json }
    }

    func setForecastSettings(bufferPct: Int) async throws -> ForecastSettings {
        let body = ForecastSettings(bufferPct: .init(rawValue: bufferPct))
        return try await call { try await client.setForecastSettings(body: .json(body)).ok.body.json }
    }

    func categoryDetail(category: String, month: String?) async throws -> CategoryDetail {
        try await call {
            try await client.getCategoryDetail(path: .init(category: category), query: .init(month: month)).ok.body.json
        }
    }
}

// MARK: Sources hub (ADR 0073)
extension LiveClient {
    func sourcesHub() async throws -> SourcesHub {
        try await call {
            try await client.getSourcesHub(query: .init(language: .init(rawValue: AppLanguage.current.rawValue))).ok.body.json
        }
    }
}
