import Foundation

/// Preview and test states for the forecast screens (ADR 0072), built from `ForecastMock` (the canvas students).
@MainActor
enum ForecastFixtures {
    enum Student { case onTrack, short, soon, overdrawn }

    static func forecast(_ student: Student, bufferPct: Int = 10, stress: Int? = nil) -> Forecast {
        let persona = switch student {
        case .onTrack: ForecastMock.onTrack
        case .short: ForecastMock.short
        case .soon: ForecastMock.soon
        case .overdrawn: ForecastMock.overdrawn
        }
        return ForecastMock.forecast(persona, bufferPct: bufferPct, stress: stress)
    }

    /// The on-track forecast with no next money found (state no_next_money).
    static var noNextMoney: Forecast {
        var forecast = forecast(.onTrack)
        forecast.state = .noNextMoney
        forecast.headline = "Penny can't see your next money yet"
        forecast.runOutDate = nil
        forecast.spare = nil
        forecast.suggestion = nil
        forecast.days = 0
        forecast.perDay = 0
        forecast.perWeek = 0
        return forecast
    }

    static func card(_ student: Student) -> ForecastCardState { .make(forecast(student)) }

    /// Eilidh's October so far (canvas 1 and 4).
    static let spending: SpendingResponse = ContractExamples.decode(#"""
    {"meta": {"data_status": "mock", "source": "sample", "as_of": "2026-10-18"},
     "month": "2026-10", "total": 820.0, "months": ["2026-07", "2026-08", "2026-09", "2026-10"],
     "categories": [
      {"category": "housing", "label": "Rent", "emoji": "🏠", "amount": 540.0, "share": 0.659, "transactions": 1, "change_pct": 0.0},
      {"category": "groceries", "label": "Groceries", "emoji": "🛒", "amount": 96.0, "share": 0.117, "transactions": 6, "change_pct": -12.7},
      {"category": "eating_out", "label": "Eating out", "emoji": "🍜", "amount": 64.0, "share": 0.078, "transactions": 8, "change_pct": 16.4},
      {"category": "entertainment", "label": "Going out", "emoji": "🎟️", "amount": 42.0, "share": 0.051, "transactions": 4, "change_pct": -12.5},
      {"category": "transport", "label": "Transport", "emoji": "🚌", "amount": 38.0, "share": 0.046, "transactions": 9, "change_pct": 0.0},
      {"category": "shopping", "label": "Shopping", "emoji": "🛍️", "amount": 28.0, "share": 0.034, "transactions": 3, "change_pct": -28.2},
      {"category": "bills", "label": "Bills", "emoji": "📱", "amount": 12.0, "share": 0.015, "transactions": 1, "change_pct": 0.0}
     ]}
    """#)

    /// Eilidh's September (the month before), for "£14 less than Sep".
    static var spendingSeptember: SpendingResponse { ForecastMock.spending(base: spending, month: "2026-09") }

    static var categoryDetail: CategoryDetail { ForecastMock.categoryDetail(spending: spending, category: "groceries")! }

    static func home(_ student: Student) -> MoneyHomeViewState {
        let forecast = forecast(student)
        var state = MoneyHomeViewState(
            header: .init(greeting: MoneyHomeViewModel.greeting(name: student == .onTrack ? "Eilidh" : "Callum"), faceEmoji: "🙂"),
            nextMove: Fixtures.NextMove.loading, widgets: Fixtures.Widgets.loading, guess: Fixtures.Guess.loading
        )
        state.content = .ready
        state.forecastPhase = .ready
        state.forecast = .make(forecast)
        state.due = ForecastDueState.make(forecast)
        state.help = ForecastHelpState.make(forecast)
        state.moneyNow = forecast.moneyNow
        state.spendingPhase = .ready
        state.spending = SpendingPieState.make(spending)
        return state
    }

    static var homeLoading: MoneyHomeViewState {
        var state = home(.onTrack)
        state.forecastPhase = .loading(.standard)
        state.forecast = nil
        state.spendingPhase = .loading(.standard)
        state.spending = nil
        state.due = nil
        state.help = nil
        state.moneyNow = nil
        return state
    }

    static var allSpending: AllSpendingState {
        let pie = SpendingPieState.make(spending, previous: spendingSeptember)
        return AllSpendingState(
            phase: .ready, pie: pie, canGoBack: true, canGoForward: false,
            fixedNote: L10n.tr("Not counted in the pie: rent £540, bills £12. Penny counts rent and bills apart.")
        )
    }

    static var category: CategoryDetailState { .make(categoryDetail, currentMonth: true) }
}
