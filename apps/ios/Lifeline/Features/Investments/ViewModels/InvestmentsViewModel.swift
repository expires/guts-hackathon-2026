import Foundation
import Observation

/// Loads `GET /v1/finance/investments`, the ISA periods, and runs the replay and scenarios.
@MainActor
@Observable
final class InvestmentsViewModel {
    static let loadingMessage = "Loading your investments"
    static let replayLabel = "Illustrative returns"
    static let currentMixID = "current"

    struct Mix: Equatable, Sendable {
        var id: String
        var label: String
        var weights: [String: Double]
    }

    static let presets: [Mix] = [
        Mix(id: "shares", label: "All shares", weights: ["global_equity": 1]),
        Mix(id: "80-20", label: "80/20", weights: ["global_equity": 0.8, "gilts": 0.2]),
        Mix(id: "60-40", label: "60/40", weights: ["global_equity": 0.6, "gilts": 0.4]),
    ]

    private let client: any LifelineClient

    private(set) var investments: InvestmentsResponse?
    private(set) var periods: IsaPeriodsResponse?
    private(set) var phase: LoadPhase = .loading(.init(message: InvestmentsViewModel.loadingMessage))
    private(set) var selectedPeriodID: String?
    private(set) var selectedMixIDs: Set<String> = ["shares", "80-20", "60-40", "current"]
    private(set) var isMonthly = true
    private(set) var backtest: Result<IsaBacktestResponse, APIError>?
    private(set) var scenarios: Result<IsaScenariosResult, APIError>?
    @ObservationIgnored var onClose: @MainActor () -> Void = {}
    @ObservationIgnored private var replayTask: Task<Void, Never>?

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: InvestmentsViewState {
        Self.makeState(
            investments: investments, periods: periods, phase: phase, selectedPeriodID: selectedPeriodID,
            selectedMixIDs: selectedMixIDs, isMonthly: isMonthly, backtest: backtest, scenarios: scenarios,
            clientKind: client.kind
        )
    }

    var actions: InvestmentsActions {
        InvestmentsActions(
            onSelectPeriod: { [weak self] in self?.selectPeriod($0) },
            onToggleMix: { [weak self] in self?.toggleMix($0) },
            onSetMonthly: { [weak self] in self?.setMonthly($0) },
            onRetry: { [weak self] in Task { await self?.load() } },
            onRetryReplay: { [weak self] in Task { await self?.runReplay() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    // MARK: Loading

    func load() async {
        phase = .loading(.init(message: Self.loadingMessage))
        let client = self.client
        do {
            async let holdings = client.investments()
            async let periods = client.isaPeriods()
            self.investments = try await holdings
            self.periods = try await periods
            selectedPeriodID = selectedPeriodID ?? self.periods?.periods.first?.id
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
            return
        }
        await runReplay()
    }

    func runReplay() async {
        backtest = nil
        scenarios = nil
        let strategies = currentStrategies()
        guard !strategies.isEmpty else { return }
        let client = self.client
        let query = IsaBacktestQuery(strategies: strategies)
        let scenarioQuery = IsaScenariosQuery(strategy: strategies[0], horizonMonths: 36)
        async let backtestResult = Self.result { try await client.isaBacktest(query) }
        async let scenarioResult = Self.result { try await client.isaScenarios(scenarioQuery) }
        let (replay, paths) = await (backtestResult, scenarioResult)
        // A newer selection may have started while this ran. Only the latest write wins.
        guard strategies == currentStrategies() else { return }
        backtest = replay
        scenarios = paths
    }

    private nonisolated static func result<T: Sendable>(_ body: @Sendable () async throws -> T) async -> Result<T, APIError> {
        do { return .success(try await body()) } catch { return .failure(APIError.map(error)) }
    }

    // MARK: Choices

    func selectPeriod(_ id: String) {
        guard selectedPeriodID != id else { return }
        selectedPeriodID = id
        restartReplay()
    }

    func toggleMix(_ id: String) {
        if selectedMixIDs.contains(id) {
            guard selectedMixIDs.count > 1 else { return }
            selectedMixIDs.remove(id)
        } else {
            selectedMixIDs.insert(id)
        }
        restartReplay()
    }

    func setMonthly(_ monthly: Bool) {
        guard isMonthly != monthly else { return }
        isMonthly = monthly
        restartReplay()
    }

    /// Waits for the replay started by the last choice. For tests.
    func waitForReplay() async { await replayTask?.value }

    private func restartReplay() {
        replayTask?.cancel()
        backtest = nil
        scenarios = nil
        replayTask = Task { [weak self] in await self?.runReplay() }
    }

    private func currentStrategies() -> [IsaStrategy] {
        Self.strategies(
            mixes: Self.availableMixes(investments).filter { selectedMixIDs.contains($0.id) },
            period: selectedPeriodID, isMonthly: isMonthly
        )
    }

    // MARK: Pure mapping (used by fixtures and tests)

    /// Three presets plus "Your current mix" when the holdings give one.
    static func availableMixes(_ investments: InvestmentsResponse?) -> [Mix] {
        var mixes = presets
        if let weights = currentWeights(investments) {
            mixes.append(Mix(id: currentMixID, label: "Your current mix", weights: weights))
        }
        return mixes
    }

    /// Shares and bonds from the holdings plus cash, scaled to add up to 1. Other assets are left out.
    static func currentWeights(_ investments: InvestmentsResponse?) -> [String: Double]? {
        guard let investments else { return nil }
        var equity = 0.0, bonds = 0.0
        for holding in investments.holdings {
            switch holding.assetClass {
            case .equity: equity += holding.value
            case .bond: bonds += holding.value
            default: break
            }
        }
        let cash = investments.cash
        let total = equity + bonds + cash
        guard total > 0, equity + bonds > 0 else { return nil }
        var weights: [String: Double] = [:]
        if equity > 0 { weights["global_equity"] = (equity / total * 10_000).rounded() / 10_000 }
        if bonds > 0 { weights["gilts"] = (bonds / total * 10_000).rounded() / 10_000 }
        if cash > 0 { weights["cash"] = (cash / total * 10_000).rounded() / 10_000 }
        // Rounding can leave the sum a hair off 1. Put the difference on the biggest weight.
        let drift = 1 - weights.values.reduce(0, +)
        if let biggest = weights.max(by: { $0.value < $1.value })?.key { weights[biggest, default: 0] += drift }
        return weights
    }

    static func strategies(mixes: [Mix], period: String?, isMonthly: Bool) -> [IsaStrategy] {
        mixes.map { mix in
            IsaStrategy(
                weights: .init(additionalProperties: mix.weights),
                technique: isMonthly ? .dca : .lumpSum,
                period: period
            )
        }
    }

    static func assetLabel(_ raw: String) -> String {
        switch raw {
        case "equity": "Shares"
        case "bond": "Bonds"
        case "cash": "Cash"
        case "property": "Property"
        case "commodity": "Gold and commodities"
        default: "Other"
        }
    }

    static func makeState(
        investments: InvestmentsResponse?,
        periods: IsaPeriodsResponse?,
        phase: LoadPhase,
        selectedPeriodID: String?,
        selectedMixIDs: Set<String>,
        isMonthly: Bool,
        backtest: Result<IsaBacktestResponse, APIError>?,
        scenarios: Result<IsaScenariosResult, APIError>?,
        clientKind: ClientKind
    ) -> InvestmentsViewState {
        let isSample = investments.map { FinanceMapping.isSample($0.meta) } ?? (clientKind == .mock)
        let mixes = availableMixes(investments)
        let mixLabels = Dictionary(uniqueKeysWithValues: mixes.map { ($0.id, $0.label) })
        let slices = (investments?.allocation.additionalProperties ?? [:])
            .sorted { $0.value > $1.value }
            .map { InvestmentsViewState.Slice(id: $0.key, label: assetLabel($0.key), percent: $0.value, percentText: FinanceMapping.percent($0.value / 100)) }
        let holdings = (investments?.holdings ?? []).map { holding -> InvestmentsViewState.HoldingRow in
            let units = holding.quantity.formatted(.number.precision(.fractionLength(0...2)))
            let detail = [ "\(units) units", holding.region ].compactMap { $0 }.joined(separator: ", ")
            return .init(id: holding.instrumentId, name: holding.name, detail: detail, value: holding.value)
        }

        let replayPhase: LoadPhase
        var points: [InvestmentsViewState.LinePoint] = []
        var results: [InvestmentsViewState.StrategyResult] = []
        var detailLabel = SampleInvesting.illustrativeLabel
        switch backtest {
        case nil:
            replayPhase = .loading(.init(message: "Replaying the past"))
        case let .failure(error):
            replayPhase = .failed(.from(error))
        case let .success(response):
            replayPhase = .ready
            detailLabel = response.label ?? detailLabel
            let selected = mixes.filter { selectedMixIDs.contains($0.id) }
            for (offset, result) in response.results.enumerated() {
                let label = selected.indices.contains(offset) ? selected[offset].label : "Mix \(offset + 1)"
                points += result.index.enumerated().map { .init(month: $0.offset, value: $0.element, series: label) }
                results.append(strategyResult(result, label: label))
            }
        }

        let pathsPhase: LoadPhase
        var fan: [InvestmentsViewState.FanPoint] = []
        var disclaimer = SampleInvesting.scenarioLabel
        switch scenarios {
        case nil:
            pathsPhase = .loading(.init(message: "Building possible paths"))
        case let .failure(error):
            pathsPhase = .failed(.from(error))
        case let .success(result):
            pathsPhase = .ready
            // The disclaimer is fixed copy. A backend label never replaces it.
            disclaimer = SampleInvesting.scenarioLabel
            let count = min(result.fan.p10.count, result.fan.p50.count, result.fan.p90.count)
            fan = (0..<count).map { .init(month: $0, low: result.fan.p10[$0], middle: result.fan.p50[$0], high: result.fan.p90[$0]) }
        }
        let basisMix = mixes.first(where: { selectedMixIDs.contains($0.id) })?.label ?? "your mix"

        return InvestmentsViewState(
            phase: phase,
            isSampleData: isSample,
            dataLabel: isSample ? "Sample data" : "Live data",
            totalValue: investments?.totalValue ?? 0,
            cash: investments?.cash ?? 0,
            slices: slices,
            holdings: holdings,
            replay: .init(
                periods: (periods?.periods ?? []).map { .init(id: $0.id, label: $0.label) },
                selectedPeriodID: selectedPeriodID,
                mixes: mixes.map { .init(id: $0.id, label: mixLabels[$0.id] ?? $0.label) },
                selectedMixIDs: selectedMixIDs,
                isMonthly: isMonthly,
                phase: replayPhase,
                points: points,
                results: results,
                dataLabel: replayLabel,
                detailLabel: detailLabel
            ),
            paths: .init(
                phase: pathsPhase,
                points: fan,
                disclaimer: disclaimer,
                basisText: "Based on \(basisMix), \(isMonthly ? "saving each month" : "one lump sum")",
                dataLabel: replayLabel
            )
        )
    }

    static func strategyResult(_ result: IsaBacktestResult, label: String) -> InvestmentsViewState.StrategyResult {
        let metrics = result.metrics
        let drop = FinanceMapping.percent(metrics.maxDrawdown)
        let recover = metrics.monthsToRecover.map { months -> String in
            months >= 24 && months % 12 == 0 ? "\(months / 12) years" : (months == 1 ? "1 month" : "\(months) months")
        } ?? "Not within this period"
        let growth = (metrics.cagr * 100).formatted(.number.precision(.fractionLength(1))) + "% a year"
        return .init(
            id: label,
            label: label,
            summary: "You put in \(Money.format(result.contributed)). It ended at \(Money.format(result.finalValue)).",
            metrics: [
                .init(id: "drop", label: "Biggest drop", value: "\(drop) down"),
                .init(id: "recover", label: "Back to start after", value: recover),
                .init(id: "growth", label: "Yearly growth", value: growth),
            ]
        )
    }
}
