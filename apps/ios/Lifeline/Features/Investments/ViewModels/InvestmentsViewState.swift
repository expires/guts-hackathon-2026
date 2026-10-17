import Foundation

/// Investments screen: what you hold, how it is split, replay your ISA through a past period, and possible paths.
struct InvestmentsViewState: Equatable, Sendable {
    struct Slice: Equatable, Sendable, Identifiable {
        var id: String
        /// "Shares", "Bonds", "Cash".
        var label: String
        /// 0 to 100.
        var percent: Double
        /// "81%".
        var percentText: String
    }

    struct HoldingRow: Equatable, Sendable, Identifiable {
        var id: String
        var name: String
        /// "41 units, Global".
        var detail: String
        var value: Double
    }

    struct Option: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
    }

    struct LinePoint: Equatable, Sendable, Identifiable {
        /// Months since the start of the period.
        var month: Int
        /// Index, start = 100.
        var value: Double
        var series: String
        var id: String { "\(series)-\(month)" }
    }

    struct MetricRow: Equatable, Sendable, Identifiable {
        var id: String
        /// "Biggest drop".
        var label: String
        /// "31% down".
        var value: String
    }

    struct StrategyResult: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        /// "You put in £9,000. It ended at £10,310."
        var summary: String
        var metrics: [MetricRow]
    }

    struct Replay: Equatable, Sendable {
        var periods: [Option]
        var selectedPeriodID: String?
        var mixes: [Option]
        var selectedMixIDs: Set<String>
        var isMonthly: Bool
        var phase: LoadPhase
        var points: [LinePoint]
        var results: [StrategyResult]
        /// "Illustrative returns"
        var dataLabel: String
        /// "Synthetic illustrative returns", from the backend.
        var detailLabel: String
    }

    struct FanPoint: Equatable, Sendable, Identifiable {
        var month: Int
        var low: Double
        var middle: Double
        var high: Double
        var id: Int { month }
    }

    struct Paths: Equatable, Sendable {
        var phase: LoadPhase
        var points: [FanPoint]
        /// Always visible: "Modelled scenarios from similar past periods. Not a forecast. Not financial advice."
        var disclaimer: String
        /// "Based on: 80/20, monthly".
        var basisText: String
        var dataLabel: String
    }

    var phase: LoadPhase
    var isSampleData: Bool
    /// "Sample data" or "Live data".
    var dataLabel: String
    var totalValue: Double
    var cash: Double
    var slices: [Slice]
    var holdings: [HoldingRow]
    var replay: Replay
    var paths: Paths
}

struct InvestmentsActions {
    var onSelectPeriod: @MainActor (String) -> Void = { _ in }
    var onToggleMix: @MainActor (String) -> Void = { _ in }
    var onSetMonthly: @MainActor (Bool) -> Void = { _ in }
    var onRetry: @MainActor () -> Void = {}
    var onRetryReplay: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
