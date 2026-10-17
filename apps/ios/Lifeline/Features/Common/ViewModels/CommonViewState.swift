import Foundation

// Plain value types shared by many ViewStates. Views and DesignSystem read them.
// They never contain generated contract types (ADR 0011).

/// Freshness of a data source.
enum DataStatus: String, Equatable, Sendable, Hashable, CaseIterable {
    case live
    case cached
    case mock
    /// The source cannot serve data right now (live mode, no data yet).
    case unavailable

    /// Plain English label for chips.
    var label: String {
        switch self {
        case .live: "live"
        case .cached: "saved copy"
        case .mock: "sample"
        case .unavailable: "unavailable"
        }
    }
}

/// One data source chip: name, freshness and an optional note such as "UK average used".
struct SourceChipState: Equatable, Sendable, Hashable, Identifiable {
    var id: String
    var name: String
    var status: DataStatus
    var note: String?
}

/// Load status for any screen that fetches data.
enum LoadPhase: Equatable, Sendable {
    case loading(LoadingViewState)
    case ready
    case failed(ErrorViewState)

    var isLoading: Bool {
        if case .loading = self { return true }
        return false
    }
}

struct LoadingViewState: Equatable, Sendable {
    var message: String

    static let standard = LoadingViewState(message: "Loading")
}

struct ErrorViewState: Equatable, Sendable {
    var title: String
    var message: String
    var canRetry: Bool
    /// The data is not there yet (409 `no_finance_data`). The view shows an "Unavailable" chip
    /// and points to onboarding instead of a crash icon.
    var isUnavailable = false

    static func from(_ error: APIError) -> ErrorViewState {
        // Rate limiting: the client already retried quietly. Calm text, no button; pull to refresh.
        if case let .server(status, _, _, _) = error, status == 429 {
            return ErrorViewState(title: "Couldn't load", message: "Pull to refresh.", canRetry: false)
        }
        if error.isNoFinanceData {
            return ErrorViewState(title: "Connect your money first", message: error.userMessage, canRetry: true, isUnavailable: true)
        }
        switch error {
        case .network:
            return ErrorViewState(title: "You are offline", message: error.userMessage, canRetry: true)
        default:
            return ErrorViewState(title: "Something went wrong", message: error.userMessage, canRetry: true)
        }
    }
}

enum StatKind: String, Equatable, Sendable, CaseIterable {
    case happiness
    case health
    case smarts
    case money

    var title: String {
        switch self {
        case .happiness: "Happiness"
        case .health: "Health"
        case .smarts: "Smarts"
        case .money: "Money"
        }
    }
}

/// One 0 to 100 stat bar.
struct StatState: Equatable, Sendable, Identifiable {
    var kind: StatKind
    var value: Int
    var id: StatKind { kind }
}

/// One row in a year-by-year feed.
struct HistoryItemState: Equatable, Sendable, Identifiable {
    var id: String
    var year: Int
    var age: Int
    var text: String
    var netWorth: Double
    /// True when the row is a decision that Rewind can go back to.
    var isDecision: Bool
}

/// Result of a choice or action.
struct OutcomeState: Equatable, Sendable {
    var text: String
    var isGood: Bool
    var moneyDelta: Double
    /// Plain English changes, for example ["-£600", "Happiness -3"].
    var changes: [String]
}

/// Chart for a lesson. Every point traces to a data source.
struct ChartState: Equatable, Sendable {
    enum Kind: Equatable, Sendable { case line, bar }

    struct Point: Equatable, Sendable, Identifiable {
        var x: Double
        var y: Double
        var label: String?
        var id: Double { x }
    }

    var kind: Kind
    var title: String
    var xLabel: String
    var yLabel: String
    var points: [Point]
    var source: SourceChipState?
}

/// One button driven by `available_actions`.
struct ActionItemState: Equatable, Sendable, Identifiable {
    var id: String
    var emoji: String
    var label: String
    var hint: String?
    var isEnabled: Bool
    /// Needs a paid extra (labelled "Demo payment").
    var isPaid: Bool
}

/// Actions for every tab screen.
struct ActionTabActions {
    var onAction: @MainActor (String) -> Void = { _ in }
    var onDismissOutcome: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
