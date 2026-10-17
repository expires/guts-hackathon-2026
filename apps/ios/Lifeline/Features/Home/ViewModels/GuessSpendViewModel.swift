import Foundation
import Observation

/// "Guess my spend" (ADR 0017): guess first, reveal after.
@MainActor
@Observable
final class GuessSpendViewModel {
    static let loadingMessage = "Loading today's spend"
    static let maxGuess: Double = 100_000

    private let client: any LifelineClient
    private(set) var prediction: SpendPrediction?
    private(set) var guesses: GuessesResponse?
    private(set) var phase: LoadPhase = .loading(.init(message: GuessSpendViewModel.loadingMessage))
    private(set) var isSubmitting = false
    private(set) var errorMessage: String?
    /// "Today" from the first load. Past days are compared with it.
    private(set) var today: String?
    var moves: [Move] = []

    @ObservationIgnored var onOpenAccuracy: @MainActor () -> Void = {}
    @ObservationIgnored var onShowMove: @MainActor (String) -> Void = { _ in }

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: GuessSpendViewState {
        var state = Self.makeState(
            prediction: prediction, guesses: guesses, phase: phase, today: today,
            moveLink: MoneyWidgetsViewModel.moveLink(for: .guess, moves: moves)
        )
        state.isSubmitting = isSubmitting
        state.errorMessage = errorMessage
        return state
    }

    var actions: GuessSpendActions {
        GuessSpendActions(
            onSubmitGuess: { [weak self] text in Task { await self?.submit(text) } },
            onSelectDay: { [weak self] date in Task { await self?.load(date: date) } },
            onBackToToday: { [weak self] in Task { await self?.load(date: nil) } },
            onOpenAccuracy: { [weak self] in self?.onOpenAccuracy() },
            onShowMove: { [weak self] in self?.onShowMove($0) },
            onRetry: { [weak self] in Task { await self?.load(date: nil) } }
        )
    }

    /// Loads one day (nil = today) and the guess history.
    func load(date: String? = nil) async {
        phase = .loading(.init(message: Self.loadingMessage))
        errorMessage = nil
        do {
            async let prediction = client.spendPrediction(date: date)
            async let guesses = client.guesses()
            let loaded = try await prediction
            if date == nil { today = loaded.date }
            self.prediction = loaded
            self.guesses = try? await guesses
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    func submit(_ text: String) async {
        guard !isSubmitting, let prediction else { return }
        guard let amount = Self.parseGuess(text) else {
            errorMessage = "Enter an amount in pounds, for example 25."
            return
        }
        isSubmitting = true
        errorMessage = nil
        defer { isSubmitting = false }
        do {
            self.prediction = try await client.makeGuess(date: prediction.date, amount: amount)
            if let refreshed = try? await client.guesses() { guesses = refreshed }
        } catch {
            errorMessage = APIError.map(error).userMessage
        }
    }

    /// Accepts "25", "£25", "25.50" and "1,200". Returns nil outside 0 to 100,000.
    static func parseGuess(_ text: String) -> Double? {
        let cleaned = text.trimmingCharacters(in: .whitespaces)
            .replacingOccurrences(of: "£", with: "")
            .replacingOccurrences(of: ",", with: "")
        guard !cleaned.isEmpty, let value = Double(cleaned), value.isFinite, value >= 0, value <= maxGuess else {
            return nil
        }
        return (value * 100).rounded() / 100
    }

    // MARK: Mapping (pure, used by fixtures and tests)

    static func makeState(
        prediction: SpendPrediction?,
        guesses: GuessesResponse?,
        phase: LoadPhase,
        today: String?,
        moveLink: MoveLinkState? = nil
    ) -> GuessSpendViewState {
        let history = (guesses?.items ?? []).map(pastDay)
        let streak = guesses?.streak ?? 0
        let best = guesses?.bestStreak ?? 0
        let streakText = (streak == 1 ? "1 day in a row" : "\(streak) days in a row") + " with 70 points or more. Best: \(best)."
        guard let prediction else {
            return GuessSpendViewState(
                phase: phase, initialGuess: initialGuess(guesses), dayChip: "Streak \(streak)", date: today ?? "", dateText: "Today", isToday: true, stage: .guessing, reveal: nil,
                weatherText: nil, history: history, pointsTotal: guesses?.pointsTotal ?? 0, streak: streak,
                bestStreak: best, streakText: streakText, accuracyText: nil,
                isSampleData: guesses.map { FinanceMapping.isSample($0.meta) } ?? false,
                isSubmitting: false, errorMessage: nil, moveLink: moveLink
            )
        }
        let isToday = today == nil || prediction.date == today
        let dayText = FinanceMapping.shortDayText(prediction.date)
        return GuessSpendViewState(
            phase: phase,
            initialGuess: initialGuess(guesses),
            dayChip: "Streak \(streak)",
            date: prediction.date,
            dateText: isToday ? "Today, \(dayText)" : dayText,
            isToday: isToday,
            stage: prediction.guess == nil ? .guessing : .revealed,
            reveal: prediction.guess.map { reveal(prediction, guess: $0) },
            weatherText: prediction.weather.map { weather in
                "\(weather.summary), \(weather.tempMaxC.formatted(.number.precision(.fractionLength(0...1))))°C"
            },
            history: history,
            pointsTotal: guesses?.pointsTotal ?? 0,
            streak: streak,
            bestStreak: best,
            streakText: streakText,
            accuracyText: "The model is off by \(FinanceMapping.pounds(prediction.model.mae)) on a typical day.",
            isSampleData: FinanceMapping.isSample(prediction.meta),
            isSubmitting: false,
            errorMessage: nil,
            moveLink: moveLink
        )
    }

    /// The last guess, else £20 (a neutral start, not a model number).
    static func initialGuess(_ guesses: GuessesResponse?) -> Double {
        guesses?.items.last?.guess.rounded() ?? 20
    }

    static func reveal(_ prediction: SpendPrediction, guess: Components.Schemas.GuessState) -> GuessSpendViewState.Reveal {
        let top = max(prediction.high, guess.amount, prediction.actual ?? 0) * 1.1
        let scaleMax = max(10, (top / 10).rounded(.up) * 10)
        func fraction(_ value: Double) -> Double { min(1, max(0, value / scaleMax)) }
        let gap = guess.amount - prediction.predicted
        let comparison: String
        if abs(gap) < 0.005 {
            comparison = "Your guess matches the model."
        } else {
            comparison = "Your guess is \(FinanceMapping.pounds(abs(gap))) \(gap < 0 ? "under" : "over") the model."
        }
        var result: String?
        if let points = guess.points {
            let beat = guess.beatModel == true ? "You beat the model." : "The model was closer."
            result = "\(beat) \(points) points."
        }
        return .init(
            guess: guess.amount,
            guessText: FinanceMapping.pounds(guess.amount),
            predicted: prediction.predicted,
            predictedText: FinanceMapping.pounds(prediction.predicted),
            low: prediction.low,
            high: prediction.high,
            rangeText: "Likely between \(FinanceMapping.pounds(prediction.low)) and \(FinanceMapping.pounds(prediction.high))",
            reasons: prediction.reasons.map { reason in
                .init(
                    id: reason.feature,
                    label: reason.label,
                    effect: reason.effect,
                    effectText: (reason.effect >= 0 ? "+" : "-") + FinanceMapping.pounds(abs(reason.effect))
                )
            },
            comparisonText: comparison,
            actual: prediction.actual,
            actualText: prediction.actual.map { "You spent \(FinanceMapping.pounds($0))." },
            points: guess.points,
            beatModel: guess.beatModel,
            resultText: result,
            rangeShortText: "\(Money.format(prediction.low)) – \(Money.format(prediction.high))",
            scaleMax: scaleMax,
            scaleMaxText: Money.format(scaleMax),
            lowFraction: fraction(prediction.low),
            highFraction: fraction(prediction.high),
            predictedFraction: fraction(prediction.predicted),
            guessFraction: fraction(guess.amount),
            isGuessInRange: guess.amount >= prediction.low && guess.amount <= prediction.high,
            baselineText: "Your normal day is \(FinanceMapping.pounds(prediction.baseline))."
        )
    }

    static func pastDay(_ day: Components.Schemas.GuessDay) -> GuessSpendViewState.PastDay {
        var parts = ["You guessed \(FinanceMapping.pounds(day.guess))"]
        if let actual = day.actual { parts[0] += ", spent \(FinanceMapping.pounds(actual))" }
        var summary = parts[0] + "."
        if let points = day.points { summary += " \(points) points." }
        if let beat = day.beatModel { summary += beat ? " You beat the model." : " The model was closer." }
        return .init(
            id: day.date,
            dateText: FinanceMapping.shortDayText(day.date),
            guess: day.guess,
            predicted: day.predicted,
            actual: day.actual,
            points: day.points,
            beatModel: day.beatModel,
            summary: summary
        )
    }
}
