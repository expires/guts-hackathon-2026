import Foundation

/// One Money tab widget: its own load state, its value, and an optional link to a related Next Move.
struct WidgetSection<Value: Equatable & Sendable>: Equatable, Sendable {
    var phase: LoadPhase
    var value: Value?
    var moveLink: MoveLinkState?

    static var loading: Self { .init(phase: .loading(.standard), value: nil, moveLink: nil) }
}

/// Link from a widget back to the Next Move card (ADR 0018).
struct MoveLinkState: Equatable, Sendable {
    var moveID: String
    /// "Your next move: Cancel 2 unused subscriptions (£264 a year)".
    var text: String
}

/// Money tab widgets under the Next Move card (ADR 0016). Every value comes from `/v1/finance/*`.
struct MoneyWidgetsViewState: Equatable, Sendable {
    struct Account: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var provider: String
        /// "Current account", "Savings", "Credit card".
        var kindLabel: String
        var balance: Double
    }

    struct Overview: Equatable, Sendable {
        /// Current and savings accounts.
        var balance: Double
        var netWorth: Double
        var balanceChart: ChartState
        var netWorthChart: ChartState
        var accounts: [Account]
        /// "As of 17 Oct 2026".
        var asOfText: String
    }

    struct Category: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String
        var label: String
        var amount: Double
        /// 0 to 1.
        var share: Double
        /// "69%".
        var shareText: String
        /// "9 payments".
        var countText: String
        /// "Up 6% on last month". Nil when unknown.
        var changeText: String?
    }

    struct Spending: Equatable, Sendable {
        /// "October 2026".
        var monthText: String
        var total: Double
        var categories: [Category]
    }

    struct Subscription: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String
        var merchant: String
        var monthlyCost: Double
        /// "£12.99 a month".
        var amountText: String
        /// "Next payment 28 Oct 2026".
        var nextPaymentText: String?
        /// "Price went up from £10.99 to £12.99 on 28 Jun 2026".
        var priceRiseText: String?
    }

    struct Subscriptions: Equatable, Sendable {
        var monthlyTotal: Double
        /// "2 subscriptions".
        var countText: String
        var items: [Subscription]
        var priceRiseCount: Int
    }

    struct Bill: Equatable, Sendable, Identifiable {
        enum Status: String, Equatable, Sendable { case upcoming, dueSoon, paid, overdue }
        var id: String
        var emoji: String
        var name: String
        var amount: Double
        /// "Due 1 Nov 2026".
        var dueText: String
        var status: Status
        /// "Due soon", "Paid".
        var statusText: String
    }

    struct Bills: Equatable, Sendable {
        var totalNext30Days: Double
        var items: [Bill]
    }

    struct Budget: Equatable, Sendable, Identifiable {
        enum Status: String, Equatable, Sendable { case ok, near, over }
        var id: String
        var emoji: String
        var label: String
        var limit: Double
        var spent: Double
        /// spent / limit. Can be above 1.
        var progress: Double
        var status: Status
        /// "£172 of £150".
        var detailText: String
        /// "£22 over", "£86 left".
        var statusText: String
    }

    struct Budgets: Equatable, Sendable {
        var monthText: String
        var items: [Budget]
    }

    struct Goal: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String
        var name: String
        var target: Double
        var saved: Double
        /// 0 to 1.
        var progress: Double
        /// "£6,200 of £20,000".
        var detailText: String
        /// "Save £429 a month to reach it by 1 Jun 2029".
        var planText: String?
    }

    var overview: WidgetSection<Overview>
    var spending: WidgetSection<Spending>
    var subscriptions: WidgetSection<Subscriptions>
    var bills: WidgetSection<Bills>
    var budgets: WidgetSection<Budgets>
    var goals: WidgetSection<[Goal]>
    /// True when any finance response is labelled mock. The View shows "Sample data".
    var isSampleData: Bool
}

struct MoneyWidgetsActions {
    /// Shows the related move in the Next Move card and scrolls to it.
    var onShowMove: @MainActor (String) -> Void = { _ in }
    /// Reloads every widget.
    var onRetry: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
