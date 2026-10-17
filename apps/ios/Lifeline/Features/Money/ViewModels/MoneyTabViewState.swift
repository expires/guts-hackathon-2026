import Foundation

struct MoneyTabViewState: Equatable, Sendable {
    struct Row: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var value: Double
    }

    var netWorth: Double
    var annualIncome: Double
    var monthlyCosts: Double
    /// What you have: cash, savings, investments, pension, home.
    var have: [Row]
    /// What you owe: mortgage, loans, student loan.
    var owe: [Row]
    /// For example "Mortgage rate 4.5%, fixed until 2031".
    var mortgageNote: String?
    var actions: [ActionItemState]
    var isBusy: Bool
    var outcome: OutcomeState?
}
