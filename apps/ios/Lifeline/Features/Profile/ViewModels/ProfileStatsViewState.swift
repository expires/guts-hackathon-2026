import Foundation

/// "Your profile": a strip of connections, then sections built from the backend's profile stats.
struct ProfileStatsViewState: Equatable, Sendable {
    /// One source in the strip at the top.
    struct Badge: Equatable, Sendable, Identifiable {
        var id: String
        var title: String
        var isConnected: Bool
        /// "Live", "Saved copy", "Sample data", "Added", "Not connected".
        var statusText: String
        /// What it gave us, spoken with the badge.
        var detail: String?
    }

    struct HabitRow: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var value: Int
    }

    struct CategoryBar: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var amount: Double
        var amountText: String
        var shareText: String
    }

    struct SpendingBody: Equatable, Sendable {
        /// "September 2026" or "October so far".
        var periodText: String
        var inText: String?
        var outText: String
        /// "Average of the last 2 full months." Nil for a part month.
        var averageText: String?
        var categories: [CategoryBar]
        var subscriptionsText: String
        var caption: String
    }

    struct PartRow: Equatable, Sendable, Identifiable {
        var id: Int
        var label: String
        var amountText: String
    }

    struct NetWorthBody: Equatable, Sendable {
        var totalText: String
        var cashText: String
        var investmentsText: String
        /// Debts and property. Nil when it is zero.
        var otherText: String?
        var parts: [PartRow]
        var caption: String
    }

    struct MixSlice: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var value: Double
        var valueText: String
        var shareText: String
        var colorIndex: Int
    }

    struct HoldingRow: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        var valueText: String
        var detail: String?
    }

    struct InvestmentsBody: Equatable, Sendable {
        var totalText: String
        var investedText: String?
        var countText: String
        var mix: [MixSlice]
        var holdings: [HoldingRow]
        var note: String?
        var caption: String
    }

    enum Content: Equatable, Sendable {
        case none
        case habits(overall: Int?, rows: [HabitRow], caption: String)
        case spending(SpendingBody)
        case netWorth(NetWorthBody)
        case investments(InvestmentsBody)
    }

    struct Section: Equatable, Sendable, Identifiable {
        var id: String
        var title: String
        var isAvailable: Bool
        /// "From Monzo", "From Trading 212", "From a sample student".
        var sourceLine: String?
        var missingHint: String?
        /// Where "Connect ..." goes when the section is unavailable.
        var jump: ConnectKind?
        var jumpTitle: String?
        var content: Content = .none
    }

    var phase: LoadPhase = .loading(.init(message: L10n.tr("Loading your profile")))
    var connections: [Badge] = []
    var sections: [Section] = []
    /// The bottom button. When there is no data at all it says "Connect your money" instead.
    var playTitle = L10n.tr("Play as yourself")
    var canPlay = false
    /// What is missing for the game, in plain words. Nil when nothing is.
    var playMissing: String?
    /// True while a pull to refresh runs.
    var isRefreshing = false
}

struct ProfileStatsActions {
    var onConnect: (ConnectKind?) -> Void = { _ in }
    var onPlay: () -> Void = {}
    var onClose: () -> Void = {}
    var onRetry: () -> Void = {}
    var onRefresh: @MainActor () async -> Void = {}

    static var noop: Self { .init() }
}
