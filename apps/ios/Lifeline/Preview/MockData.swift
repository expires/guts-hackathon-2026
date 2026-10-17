import Foundation

/// Canned responses for `MockClient`.
///
/// - `.contract`: the contract examples (`contracts/openapi.yaml`). Unit tests, previews and the Playground use them.
/// - `.recorded`: real engine responses for the demo persona, recorded from the API into `Preview/Recorded/<operationId>.json`
///   (`make ios-record-mock`). The app's mock client (Mock build on the phone, `-mockClient`, `-uiTestingMock`) uses them.
///   Each endpoint without a recorded file falls back to its contract example.
struct MockData: Sendable {
    var characters: CharactersResponse
    var life: Life
    var summary: LifeSummary
    var lives: LivesResponse
    var concepts: [Concept]
    var challenges: [Challenge]
    var evaluation: Evaluation
    var sources: [SourceStatus]
    var financeOverview: FinanceOverview
    var spending: SpendingResponse
    var subscriptions: SubscriptionsResponse
    var bills: BillsResponse
    var budgets: BudgetsResponse
    var goals: GoalsResponse
    var financeProfile: FinanceProfile
    var spendPrediction: SpendPrediction
    var guesses: GuessesResponse
    var predictionEvaluation: PredictionEvaluation
    var nextMove: NextMoveResponse
    var testMoveResult: TestMoveResult
    var plan: PlanResponse

    /// "Today" for the guess game: the prediction's date.
    var today: String { spendPrediction.date }

    static let contract = MockData(
        characters: ContractExamples.characters,
        life: ContractExamples.lifeReadyToAge,
        summary: ContractExamples.summary,
        lives: ContractExamples.lives,
        concepts: ContractExamples.concepts,
        challenges: ContractExamples.challenges,
        evaluation: ContractExamples.evaluation,
        sources: ContractExamples.sources,
        financeOverview: ContractExamples.financeOverview,
        spending: ContractExamples.spending,
        subscriptions: ContractExamples.subscriptions,
        bills: ContractExamples.bills,
        budgets: ContractExamples.budgets,
        goals: ContractExamples.goals,
        financeProfile: ContractExamples.financeProfile,
        spendPrediction: ContractExamples.spendPrediction,
        guesses: ContractExamples.guesses,
        predictionEvaluation: ContractExamples.predictionEvaluation,
        nextMove: ContractExamples.nextMove,
        testMoveResult: ContractExamples.testMoveResult,
        plan: ContractExamples.plan
    )

    /// Recorded responses from the app bundle, with contract examples for missing files.
    static let recorded: MockData = {
        var data = MockData.contract
        func load<T: Decodable>(_ operationID: String) -> T? {
            guard let url = Bundle.main.url(forResource: operationID, withExtension: "json"),
                  let raw = try? Data(contentsOf: url) else { return nil }
            return try? ContractExamples.decoder.decode(T.self, from: raw)
        }
        if let value: CharactersResponse = load("listCharacters") { data.characters = value }
        if var value: Life = load("createLife") {
            value.pendingEvents = []
            data.life = value
        }
        if let value: LifeSummary = load("getLifeSummary") { data.summary = value }
        if let value: LivesResponse = load("listLives") { data.lives = value }
        if let value: Components.Schemas.ConceptsResponse = load("listConcepts") { data.concepts = value.concepts }
        if let value: Evaluation = load("getEvaluation") { data.evaluation = value }
        if let value: Components.Schemas.SourcesResponse = load("listSources") { data.sources = value.sources }
        if let value: FinanceOverview = load("getFinanceOverview") { data.financeOverview = value }
        if let value: SpendingResponse = load("getFinanceSpending") { data.spending = value }
        if let value: SubscriptionsResponse = load("listSubscriptions") { data.subscriptions = value }
        if let value: BillsResponse = load("listBills") { data.bills = value }
        if let value: BudgetsResponse = load("listBudgets") { data.budgets = value }
        if let value: GoalsResponse = load("listGoals") { data.goals = value }
        if let value: FinanceProfile = load("getFinanceProfile") { data.financeProfile = value }
        if let value: SpendPrediction = load("getSpendPrediction") { data.spendPrediction = value }
        if let value: GuessesResponse = load("listGuesses") { data.guesses = value }
        if let value: PredictionEvaluation = load("getPredictionEvaluation") { data.predictionEvaluation = value }
        if let value: NextMoveResponse = load("getNextMove") { data.nextMove = value }
        if let value: TestMoveResult = load("testNextMove") { data.testMoveResult = value }
        if let value: PlanResponse = load("getPlan") { data.plan = value }
        return data
    }()

    /// Today's prediction before the user guesses.
    var spendPredictionBeforeGuess: SpendPrediction {
        var prediction = spendPrediction
        prediction.guess = nil
        return prediction
    }
}
