import Foundation

/// "Guess my spend" card (ADR 0017). The prediction, range and reasons stay out of the state
/// until the user has guessed: `reveal` is nil in the `.guessing` stage.
struct GuessSpendViewState: Equatable, Sendable {
    enum Stage: Equatable, Sendable {
        /// No guess yet. Show only the guess entry.
        case guessing
        /// Guess made. Show the prediction, range, reasons and (for a past day) the actual.
        case revealed
    }

    struct Reason: Equatable, Sendable, Identifiable {
        var id: String
        /// "It is Friday".
        var label: String
        /// GBP vs a typical day.
        var effect: Double
        /// "+£9.80", "-£1.70".
        var effectText: String
    }

    struct Reveal: Equatable, Sendable {
        var guess: Double
        /// "£30.00".
        var guessText: String
        var predicted: Double
        /// "£38.40".
        var predictedText: String
        var low: Double
        var high: Double
        /// "Likely between £12.00 and £71.50".
        var rangeText: String
        /// Top 3 by size.
        var reasons: [Reason]
        /// "Your guess is £8.40 under the model."
        var comparisonText: String
        /// Set when the day is over.
        var actual: Double?
        /// "You spent £24.10."
        var actualText: String?
        var points: Int?
        var beatModel: Bool?
        /// "You beat the model. 96 points." Nil until the actual is known.
        var resultText: String?
    }

    struct PastDay: Equatable, Sendable, Identifiable {
        /// YYYY-MM-DD.
        var id: String
        /// "Fri 16 Oct".
        var dateText: String
        var guess: Double
        var predicted: Double
        var actual: Double?
        var points: Int?
        var beatModel: Bool?
        /// "You guessed £25.00, spent £24.10. 96 points. You beat the model."
        var summary: String
    }

    var phase: LoadPhase
    /// YYYY-MM-DD of the shown day.
    var date: String
    /// "Today, Sat 17 Oct" or "Fri 16 Oct".
    var dateText: String
    var isToday: Bool
    var stage: Stage
    var reveal: Reveal?
    /// "Light rain, 13.5°C". Not a spend number, so it shows before the guess.
    var weatherText: String?
    var history: [PastDay]
    var pointsTotal: Int
    var streak: Int
    var bestStreak: Int
    /// "3 days in a row with 70 points or more. Best: 5."
    var streakText: String
    /// "The model is off by £11.30 on a typical day."
    var accuracyText: String?
    var isSampleData: Bool
    var isSubmitting: Bool
    /// Invalid entry or a server error such as "You already guessed for this day."
    var errorMessage: String?
    var moveLink: MoveLinkState?
}

struct GuessSpendActions {
    /// Raw text from the entry field, for example "30" or "£30.50".
    var onSubmitGuess: @MainActor (String) -> Void = { _ in }
    /// Shows a past day (YYYY-MM-DD) with its actual.
    var onSelectDay: @MainActor (String) -> Void = { _ in }
    var onBackToToday: @MainActor () -> Void = {}
    /// Opens model accuracy (`/v1/finance/prediction/evaluation`).
    var onOpenAccuracy: @MainActor () -> Void = {}
    var onShowMove: @MainActor (String) -> Void = { _ in }
    var onRetry: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
