import Foundation

/// Decoded contract examples (`contracts/openapi.yaml` `components.examples`).
/// Used by `MockClient`, by `Fixtures` and by unit tests.
enum ContractExamples {
    static let characters: CharactersResponse = decode(PreviewJSON.characters)
    static let life: Life = decode(PreviewJSON.life)
    static let ageResult: AgeResult = decode(PreviewJSON.ageResult)
    static let choiceResult: ChoiceResult = decode(PreviewJSON.choiceResult)
    static let choiceResultDefault: ChoiceResult = decode(PreviewJSON.choiceResultDefault)
    static let actionResult: ActionResult = decode(PreviewJSON.actionResult)
    static let rewindResult: RewindResult = decode(PreviewJSON.rewindResult)
    static let summary: LifeSummary = decode(PreviewJSON.summary)
    static let concepts: [Concept] = (decode(PreviewJSON.concepts) as Components.Schemas.ConceptsResponse).concepts
    static let challenges: [Challenge] = (decode(PreviewJSON.challenges) as Components.Schemas.ChallengesResponse).challenges
    static let decision: Decision = decode(PreviewJSON.decision)
    static let decisionProfile: DecisionProfile = (decode(PreviewJSON.decisionRequest) as Components.Schemas.DecisionRequest).profile
    static let evaluation: Evaluation = decode(PreviewJSON.evaluation)
    static let room: Room = decode(PreviewJSON.room)
    static let bankAuthLink: BankAuthLink = decode(PreviewJSON.bankAuthLink)
    static let bankSummary: BankSummary = decode(PreviewJSON.bankSummary)
    static let purchase: PurchaseVerifyResponse = decode(PreviewJSON.purchaseVerifyResponse)
    static let sources: [SourceStatus] = (decode(PreviewJSON.sources) as Components.Schemas.SourcesResponse).sources

    static let lives: LivesResponse = decode(PreviewJSON.lives)

    // Money tab (ADR 0016, 0017)
    static let financeOverview: FinanceOverview = decode(PreviewJSON.financeOverview)
    static let spending: SpendingResponse = decode(PreviewJSON.spending)
    static let subscriptions: SubscriptionsResponse = decode(PreviewJSON.subscriptions)
    static let bills: BillsResponse = decode(PreviewJSON.bills)
    static let budgets: BudgetsResponse = decode(PreviewJSON.budgets)
    static let goals: GoalsResponse = decode(PreviewJSON.goals)
    static let goal: SavingsGoal = decode(PreviewJSON.goal)
    static let financeProfile: FinanceProfile = decode(PreviewJSON.financeProfile)
    /// The contract example already holds a guess. `spendPredictionBeforeGuess` removes it.
    static let spendPrediction: SpendPrediction = decode(PreviewJSON.spendPrediction)
    static let guesses: GuessesResponse = decode(PreviewJSON.guesses)
    static let predictionEvaluation: PredictionEvaluation = decode(PreviewJSON.predictionEvaluation)

    // Next Move (ADR 0018)
    static let nextMove: NextMoveResponse = decode(PreviewJSON.nextMove)
    static let testMoveResult: TestMoveResult = decode(PreviewJSON.testMoveResult)
    static let planItem: PlanItem = decode(PreviewJSON.planItem)
    static let plan: PlanResponse = decode(PreviewJSON.plan)

    /// Today's prediction before the user guesses: the number, range and reasons stay hidden in the UI.
    static var spendPredictionBeforeGuess: SpendPrediction {
        var prediction = spendPrediction
        prediction.guess = nil
        return prediction
    }

    static var event: LifeEvent { ageResult.events[0] }
    static var lesson: Lesson { choiceResult.lesson! }

    /// The example life with its open event removed, so AGE is available.
    static var lifeReadyToAge: Life {
        var life = life
        life.pendingEvents = []
        return life
    }

    static func decode<T: Decodable>(_ json: String) -> T {
        do {
            return try decoder.decode(T.self, from: Data(json.utf8))
        } catch {
            fatalError("ContractExamples cannot decode \(T.self): \(error)")
        }
    }

    /// Accepts ISO 8601 date-times with or without a time zone.
    /// The `Sources` example has `fetched_at` without one (see W6 report).
    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let raw = try decoder.singleValueContainer().decode(String.self)
            let withZone = ISO8601DateFormatter()
            if let date = withZone.date(from: raw) { return date }
            let withoutZone = ISO8601DateFormatter()
            withoutZone.formatOptions = [.withFullDate, .withTime, .withColonSeparatorInTime, .withDashSeparatorInDate]
            withoutZone.timeZone = TimeZone(identifier: "UTC")
            if let date = withoutZone.date(from: raw) { return date }
            throw DecodingError.dataCorrupted(.init(codingPath: decoder.codingPath, debugDescription: "Bad date \(raw)"))
        }
        return decoder
    }()
}
