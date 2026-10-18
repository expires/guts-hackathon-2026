import Foundation
import Observation

/// Loads `GET /v1/profile/stats` and maps it to the page. Every figure comes from the response.
@MainActor
@Observable
final class ProfileStatsViewModel {
    private let load: @Sendable () async throws -> ProfileStats
    private(set) var state = ProfileStatsViewState()

    @ObservationIgnored var onConnect: @MainActor (ConnectKind?) -> Void = { _ in }
    @ObservationIgnored var onPlay: @MainActor () -> Void = {}
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(client: any LifelineClient) {
        load = { try await client.profileStats() }
    }

    init(load: @escaping @Sendable () async throws -> ProfileStats) {
        self.load = load
    }

    var actions: ProfileStatsActions {
        ProfileStatsActions(
            onConnect: { [weak self] kind in self?.onConnect(kind) },
            onPlay: { [weak self] in
                guard let self else { return }
                // Without any data the button leads to the connect step instead.
                if state.canPlay { onPlay() } else { onConnect(nil) }
            },
            onClose: { [weak self] in self?.onClose() },
            onRetry: { [weak self] in Task { await self?.reload() } },
            onRefresh: { [weak self] in await self?.reload() }
        )
    }

    func reload() async {
        if case .loading = state.phase {} else { state.isRefreshing = true }
        defer { state.isRefreshing = false }
        do {
            apply(try await load())
        } catch {
            if state.sections.isEmpty { state.phase = .failed(.from(APIError.map(error))) }
        }
    }

    func apply(_ stats: ProfileStats) {
        var next = Self.makeState(stats)
        next.isRefreshing = state.isRefreshing
        state = next
    }

    // MARK: Pure mapping (fixtures and tests)

    static func makeState(_ stats: ProfileStats) -> ProfileStatsViewState {
        var state = ProfileStatsViewState()
        state.phase = .ready
        state.connections = stats.connections.map(badge)
        state.sections = stats.sections.map { section($0, stats: stats) }
        let available = state.sections.filter(\.isAvailable)
        state.canPlay = !available.isEmpty
        if available.isEmpty {
            state.playTitle = L10n.tr("Connect your money")
            state.playMissing = L10n.tr("Penny needs your balance or your transactions to start. Connect your money first.")
        } else {
            state.playTitle = L10n.tr("Play as yourself")
            let missing = state.sections.filter { !$0.isAvailable }.map { $0.title.lowercased() }
            if !missing.isEmpty {
                state.playMissing = L10n.tr("Missing: \(missing.joined(separator: ", ")). Penny uses what she has and asks for the rest.")
            }
        }
        return state
    }

    static func badge(_ c: ProfileConnection) -> ProfileStatsViewState.Badge {
        let status: String
        if !c.connected {
            status = L10n.tr("Not connected")
        } else {
            switch (c.dataStatus, c.id) {
            case (.some(.mock), _): status = L10n.tr("Sample data")
            case (.some(.cached), _): status = L10n.tr("Saved copy")
            case (_, .monzo), (_, .trading212): status = L10n.tr("Live")
            default: status = L10n.tr("Added")
            }
        }
        return .init(id: c.id.rawValue, title: c.title, isConnected: c.connected, statusText: status, detail: c.provides)
    }

    static func sourceLine(_ sources: [String], stats: ProfileStats) -> String? {
        let names = sources.compactMap { id -> String? in
            switch id {
            case "monzo": "Monzo"
            case "trading212": "Trading 212"
            case "statement": L10n.tr("your statement")
            case "manual": L10n.tr("the numbers you entered")
            case "sample": L10n.tr("a sample student")
            default: nil
            }
        }
        guard !names.isEmpty else { return nil }
        let joined = names.count == 1 ? names[0] : names.dropLast().joined(separator: ", ") + L10n.tr(" and ") + names[names.count - 1]
        return L10n.tr("From \(joined)")
    }

    static func section(_ s: ProfileSection, stats: ProfileStats) -> ProfileStatsViewState.Section {
        let id = s.id.rawValue
        var out = ProfileStatsViewState.Section(id: id, title: s.title, isAvailable: s.available)
        guard s.available else {
            out.missingHint = s.missingHint
            let jump: ConnectKind = id == "investments" ? .trading212 : .monzo
            out.jump = jump
            out.jumpTitle = jump == .trading212 ? L10n.tr("Connect Trading 212") : L10n.tr("Connect your money")
            return out
        }
        out.sourceLine = sourceLine((s.sources ?? []).map(\.rawValue), stats: stats)
        if let habits = s.habits {
            out.content = .habits(overall: habits.overall.map { Int($0) }, rows: habitRows(habits),
                                  caption: L10n.tr("Each score is out of 100 and higher is better. These are ratios, never amounts."))
        } else if let spending = s.spending {
            out.content = .spending(spendingBody(spending))
        } else if let worth = s.netWorth {
            out.content = .netWorth(netWorthBody(worth))
        } else if let inv = s.investments {
            out.content = .investments(investmentsBody(inv))
        }
        return out
    }

    static func habitRows(_ habits: HabitScore) -> [ProfileStatsViewState.HabitRow] {
        let c = habits.components
        let all: [(String, String, Int?)] = [
            ("savings_rate", L10n.tr("Saving"), c.savingsRate.map { Int($0) }),
            ("months_of_cover", L10n.tr("Money in the bank"), c.monthsOfCover.map { Int($0) }),
            ("spend_stability", L10n.tr("Steady spending"), c.spendStability.map { Int($0) }),
            ("discretionary_share", L10n.tr("Spending on wants"), c.discretionaryShare.map { Int($0) }),
            ("subscription_creep", L10n.tr("Subscriptions"), c.subscriptionCreep.map { Int($0) }),
            ("debt_pressure", L10n.tr("Debt"), c.debtPressure.map { Int($0) }),
        ]
        return all.compactMap { id, label, value in value.map { .init(id: id, label: label, value: $0) } }
    }

    static func monthName(_ month: String) -> String {
        let parts = month.split(separator: "-")
        guard parts.count == 2, let year = Int(parts[0]), let m = Int(parts[1]), (1...12).contains(m) else { return month }
        var calendar = Calendar(identifier: .gregorian)
        calendar.locale = Money.locale
        return "\(calendar.monthSymbols[m - 1]) \(year)"
    }

    static func spendingBody(_ s: Components.Schemas.SpendingSummary) -> ProfileStatsViewState.SpendingBody {
        let month = monthName(s.month)
        let period = s.partial ? L10n.tr("\(month) so far") : month
        let subs = s.subscriptionsCount == 1
            ? L10n.tr("1 subscription, \(Money.format(s.subscriptionsMonthly)) a month")
            : L10n.tr("\(s.subscriptionsCount) subscriptions, \(Money.format(s.subscriptionsMonthly)) a month")
        let top = s.topCategories.map { c in
            ProfileStatsViewState.CategoryBar(
                id: c.category.rawValue, label: c.label, amount: c.amount, amountText: Money.format(c.amount),
                shareText: "\(Int((c.share * 100).rounded()))%"
            )
        }
        return .init(
            periodText: period,
            inText: s.monthlyIn.map { L10n.tr("\(Money.format($0)) in") },
            outText: L10n.tr("\(Money.format(s.monthlyOut)) out"),
            averageText: s.partial ? nil : (s.monthsUsed == 1
                ? L10n.tr("Last full month")
                : L10n.tr("Average of the last \(s.monthsUsed) full months")),
            categories: top,
            subscriptionsText: subs,
            caption: L10n.tr("Your biggest spending areas in \(month). Each bar is the pounds spent.")
        )
    }

    static func netWorthBody(_ w: Components.Schemas.NetWorthSummary) -> ProfileStatsViewState.NetWorthBody {
        .init(
            totalText: Money.format(w.netWorth),
            cashText: Money.format(w.cash),
            investmentsText: Money.format(w.investments),
            otherText: w.other == 0 ? nil : Money.format(w.other),
            parts: w.parts.enumerated().map { .init(id: $0.offset, label: $0.element.label, amountText: Money.format($0.element.amount)) },
            caption: L10n.tr("Net worth is what you hold minus what you owe. Investments are never counted as cash.")
        )
    }

    /// "12.5 shares · 18% of your investments". Share only when the invested total is known.
    static func holdingDetail(_ h: Components.Schemas.Holding, invested: Double?) -> String {
        let qty = h.quantity.formatted(.number.precision(.fractionLength(0...4)))
        var parts = [h.quantity == 1 ? L10n.tr("1 share") : L10n.tr("\(qty) shares")]
        if let invested, invested > 0 {
            parts.append(L10n.tr("\(Int((h.value / invested * 100).rounded()))% of your investments"))
        }
        return parts.joined(separator: " · ")
    }

    static func investmentsBody(_ i: Components.Schemas.InvestmentSummary) -> ProfileStatsViewState.InvestmentsBody {
        .init(
            totalText: Money.format(i.totalValue),
            investedText: i.investedValue.map { Money.format($0) },
            countText: i.holdingsCount == 1 ? L10n.tr("1 holding") : L10n.tr("\(i.holdingsCount) holdings"),
            mix: (i.mix ?? []).enumerated().map { offset, slice in
                .init(id: slice.assetClass.rawValue, label: slice.label, value: slice.value, valueText: Money.format(slice.value),
                      shareText: "\(Int(slice.sharePct.rounded()))%", colorIndex: offset)
            },
            holdings: (i.topHoldings ?? []).map { h in
                .init(id: h.instrumentId, name: h.name, valueText: Money.format(h.value),
                      detail: holdingDetail(h, invested: i.investedValue))
            },
            note: i.note,
            caption: L10n.tr("Your investments split by type. Values come from Trading 212.")
        )
    }
}
