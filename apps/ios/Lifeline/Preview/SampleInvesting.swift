import Foundation

/// Labelled sample data for connections, investing and habits. Used by `MockClient`, fixtures and the Playground.
/// Everything here is made up. The UI shows "Sample data" and "Illustrative returns" next to it.
enum SampleInvesting {
    static let illustrativeLabel = "Synthetic illustrative returns"
    static let scenarioLabel = "Modelled scenarios from similar past periods. Not a forecast. Not financial advice."

    static func connections(monzo: ProviderConnection? = nil, trading212: ProviderConnection? = nil) -> ConnectionsResponse {
        ConnectionsResponse(providers: [
            monzo ?? ProviderConnection(provider: .monzo, connected: false, dataStatus: .mock, oauthAvailable: false),
            trading212 ?? ProviderConnection(provider: .trading212, connected: false, dataStatus: .mock),
        ])
    }

    static let monzoConnected = ProviderConnection(
        provider: .monzo, connected: true, dataStatus: .live, hint: "…a1b2", oauthAvailable: true,
        history: HistoryStatus(synced: true, oldest: "2024-10-18", count: 1342)
    )

    static let monzoWaitingForApproval = ProviderConnection(
        provider: .monzo, connected: true, dataStatus: .live, hint: "…a1b2", oauthAvailable: true,
        history: HistoryStatus(synced: false, count: 0, lastError: "auth")
    )

    static let trading212Connected = ProviderConnection(
        provider: .trading212, connected: true, dataStatus: .live, hint: "…9f3c"
    )

    static let investments = InvestmentsResponse(
        meta: FinanceMeta(dataStatus: .mock, source: "fixtures", asOf: "2026-10-17", label: "Sample data"),
        holdings: [
            Holding(instrumentId: "VWRL", name: "Vanguard FTSE All-World", quantity: 41.2, value: 4_820.40, assetClass: .equity, region: "Global"),
            Holding(instrumentId: "VUSA", name: "Vanguard S&P 500", quantity: 18.0, value: 1_702.10, assetClass: .equity, region: "US"),
            Holding(instrumentId: "VGOV", name: "Vanguard UK Gilts", quantity: 60.0, value: 1_130.55, assetClass: .bond, region: "UK"),
            Holding(instrumentId: "SGLN", name: "Physical Gold", quantity: 9.0, value: 412.80, assetClass: .commodity),
        ],
        totalValue: 8_065.85,
        cash: 240.00,
        allocation: .init(additionalProperties: ["equity": 80.9, "bond": 14.0, "commodity": 5.1])
    )

    static let habits: HabitFactors = {
        func factor(_ id: HabitFactor.IdPayload, _ label: String, _ explainer: String, _ raw: Double?, _ score: Int?, reason: String? = nil) -> HabitFactor {
            HabitFactor(id: id, label: label, explainer: explainer, raw: raw, score: score, reason: reason)
        }
        return HabitFactors(
            window: HabitWindow(months: 6, end: "2026-09-30"),
            factors: [
                factor(.savingsRate, "Money you keep", "The share of what you earn that you do not spend.", 0.18, 70),
                factor(.runwayMonths, "Cushion", "How many months you could cover with your savings.", 3.4, 58),
                factor(.spendStability, "Steady spending", "How much your spending jumps around from month to month.", 0.12, 76),
                factor(.discretionaryShare, "Treats", "The share of spending on things you could skip.", 0.31, 52),
                factor(.subscriptionCreep, "Subscriptions", "Whether your regular payments are creeping up.", 0.04, 81),
                factor(.isaConcentration, "Spread of your investments", "Whether your ISA leans on one kind of investment.", nil, nil, reason: "Connect Trading212 to see this."),
                factor(.shockResilience, "Bumps in the road", "How a surprise bill would affect you.", 0.6, 64),
            ],
            overall: 67
        )
    }()

    static let periods = IsaPeriodsResponse(
        periods: [
            IsaPeriod(id: "gfc_2008", label: "The 2008 financial crisis", start: "2007-10", end: "2012-12"),
            IsaPeriod(id: "covid_2020", label: "The 2020 shock", start: "2019-06", end: "2023-12"),
            IsaPeriod(id: "rates_2022", label: "Rising prices and rates, 2022", start: "2021-06", end: "2025-12"),
        ],
        assets: ["global_equity", "uk_equity", "gilts", "cash"],
        label: illustrativeLabel,
        dataStatus: .mock
    )

    /// A deterministic made-up index: more equity weight means bigger swings and a higher drift.
    static func backtest(_ query: IsaBacktestQuery) -> IsaBacktestResponse {
        let months = 60
        let labels = (0..<months).map { String(format: "%04d-%02d", 2007 + ($0 + 9) / 12, ($0 + 9) % 12 + 1) }
        let results = query.strategies.map { strategy -> IsaBacktestResult in
            let equity = strategy.weights.additionalProperties
                .filter { $0.key.contains("equity") }.values.reduce(0, +)
            let swing = 0.4 + equity
            var level = 100.0
            var series: [Double] = []
            for step in 0..<months {
                let wave = sin(Double(step) / 5.0) * 1.4 * swing + (step > 12 && step < 24 ? -2.2 * swing : 0.4 * swing)
                level = max(40, level * (1 + (wave + 0.35 * swing) / 100))
                series.append((level * 10).rounded() / 10)
            }
            let monthly = query.monthlyContribution ?? 150
            let contributed = strategy.technique == .lumpSum ? monthly * 12 : monthly * Double(months)
            let peak = series.reduce(100, max)
            let trough = series.min() ?? 100
            return IsaBacktestResult(
                period: strategy.period ?? "gfc_2008",
                label: "The 2008 financial crisis",
                months: labels,
                index: series,
                metrics: IsaBacktestMetrics(
                    cagr: ((series.last ?? 100) / 100 - 1) / 5,
                    volatility: 0.05 + 0.1 * swing,
                    maxDrawdown: min(0.6, max(0.03, (peak - trough) / peak)),
                    monthsToRecover: 24 + Int(equity * 14),
                    worst12m: -0.08 - 0.2 * equity
                ),
                contributed: contributed,
                finalValue: contributed * (series.last ?? 100) / 100,
                moneyWeightedReturn: 0.03 + 0.02 * equity,
                dataStatus: .mock,
                dataLabel: illustrativeLabel
            )
        }
        return IsaBacktestResponse(
            results: results,
            monthlyContribution: query.monthlyContribution ?? 150,
            contributionSource: query.monthlyContribution == nil ? ._default : .request,
            label: illustrativeLabel,
            dataStatus: .mock
        )
    }

    static func scenarios(_ query: IsaScenariosQuery) -> IsaScenariosResult {
        let horizon = query.horizonMonths ?? 36
        let p50 = (0...horizon).map { 100 * pow(1.0045, Double($0)) }
        let p10 = (0...horizon).map { 100 * pow(1.0045, Double($0)) * (1 - 0.0075 * Double($0).squareRoot() * 2.2) }
        let p90 = (0...horizon).map { 100 * pow(1.0045, Double($0)) * (1 + 0.0075 * Double($0).squareRoot() * 2.2) }
        func round1(_ values: [Double]) -> [Double] { values.map { ($0 * 10).rounded() / 10 } }
        return IsaScenariosResult(
            paths: [ScenarioPath(startMonth: "2009-03", index: round1(p50))],
            fan: ScenarioFan(p10: round1(p10), p50: round1(p50), p90: round1(p90)),
            horizonMonths: horizon,
            label: scenarioLabel,
            dataStatus: .mock,
            dataLabel: illustrativeLabel
        )
    }
}
