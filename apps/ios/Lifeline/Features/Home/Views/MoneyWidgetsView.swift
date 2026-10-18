import Charts
import SwiftUI

/// Money details (handoff Money-More), opened from the Money tab tiles and "See all".
/// Each part loads and fails on its own.
struct MoneyWidgetsView: View {
    let state: MoneyWidgetsViewState
    var actions: MoneyWidgetsActions = .noop
    /// Which detail to show. `.all` shows spending, bills, subscriptions, budgets and goals.
    var detail: MoneyDetail = .all

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            switch detail {
            case .accounts:
                section(state.overview, id: "accounts") { AccountsCard(overview: $0) }
            case .netWorth:
                if state.overview.value?.showsNetWorth != false {
                    section(state.overview, id: "overview") { NetWorthCard(overview: $0) }
                }
                section(state.overview, id: "accounts") { AccountsCard(overview: $0) }
            case .all:
                section(state.spending, id: "spending") { SpendingSummary(spending: $0) }
                section(state.bills, id: "bills") { BillsList(bills: $0) }
                section(state.subscriptions, id: "subscriptions") { SubscriptionsList(subscriptions: $0) }
                section(state.budgets, id: "budgets") { BudgetsList(budgets: $0) }
                section(state.goals, id: "goals") { GoalsList(goals: $0) }
            }
        }
    }

    @ViewBuilder
    private func section<Value: Equatable & Sendable, Content: View>(
        _ section: WidgetSection<Value>,
        id: String,
        @ViewBuilder content: (Value) -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            switch section.phase {
            case let .loading(loading):
                LoadingStateView(state: loading)
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                if let value = section.value { content(value) }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("widget.\(id)")
    }
}

private struct NetWorthCard: View {
    let overview: MoneyWidgetsViewState.Overview

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            Text("Net worth").font(.llLabel).foregroundStyle(Theme.Palette.muted)
            Text(Money.format(overview.netWorth)).font(.llTitle)
            Chart {
                ForEach(overview.netWorthChart.points) { point in
                    LineMark(x: .value("Day", point.x), y: .value("£", point.y))
                        .foregroundStyle(Theme.Palette.money)
                        .lineStyle(StrokeStyle(lineWidth: 4, lineCap: .round, lineJoin: .round))
                }
                if let last = overview.netWorthChart.points.last {
                    PointMark(x: .value("Day", last.x), y: .value("£", last.y))
                        .symbol { Circle().fill(Theme.Palette.money).overlay(Circle().stroke(Theme.Palette.ink, lineWidth: 2.5)).frame(width: 10, height: 10) }
                }
            }
            .chartXAxis(.hidden)
            .chartYAxis { AxisMarks { _ in AxisGridLine().foregroundStyle(Theme.Palette.rule) } }
            .frame(height: 84)
            .accessibilityLabel(overview.netWorthChangeText ?? L10n.tr("Net worth over time"))
            // At most 4 month labels (first, last and 2 between), so the row never gets wider than the card.
            let labels = Self.axisLabels(overview.monthLabels)
            HStack(spacing: 0) {
                ForEach(labels.indices, id: \.self) { index in
                    Text(labels[index]).font(.llLabel).foregroundStyle(Theme.Palette.muted).lineLimit(1)
                    if index < labels.count - 1 { Spacer(minLength: Theme.Spacing.s) }
                }
            }
            if let change = overview.netWorthChangeText {
                Text(change).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
            if !overview.netWorthParts.isEmpty {
                CalculationList(title: L10n.tr("How we worked it out"), parts: overview.netWorthParts, total: overview.netWorth, totalLabel: "Net worth")
                    .accessibilityIdentifier("money.netWorthCalculation")
            }
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, 14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(HandCut((18, 24, 16, 22), (22, 16, 24, 18)))
    }

    static func axisLabels(_ all: [String]) -> [String] {
        guard all.count > 4 else { return all }
        let last = all.count - 1
        return [0, last / 3, (2 * last) / 3, last].map { all[$0] }
    }
}

private struct AccountsCard: View {
    let overview: MoneyWidgetsViewState.Overview

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            Text("In your account").font(.llLabel).foregroundStyle(Theme.Palette.muted)
            Text(Money.format(overview.balance)).font(.llHero)
            if !overview.balanceParts.isEmpty {
                CalculationList(title: L10n.tr("How we worked it out"), parts: overview.balanceParts, total: overview.balance, totalLabel: "In your account")
                    .padding(Theme.Spacing.l)
                    .inkSurface(.cardAlt)
                    .accessibilityIdentifier("money.balanceCalculation")
            }
            RowGroup(title: "Accounts") {
                ForEach(overview.accounts) { account in
                    ListRow(
                        icon: account.kindLabel == "Credit card" ? .card : (account.kindLabel == "Savings" ? .savings : .bank),
                        title: account.name,
                        subtitle: "\(account.kindLabel), \(account.provider)",
                        trailing: Money.format(account.balance),
                        showsChevron: false
                    )
                }
            }
            Text(overview.asOfText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
        }
    }
}

/// The sum behind a shown total: one row per part, a rule, then the total. Entered data only.
private struct CalculationList: View {
    let title: String
    let parts: [MoneyWidgetsViewState.Part]
    let total: Double
    let totalLabel: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(title).font(.llLabelBold).foregroundStyle(Theme.Palette.muted)
            ForEach(parts) { part in
                HStack(alignment: .firstTextBaseline) {
                    Text(part.label).font(.llLabel).fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: Theme.Spacing.s)
                    Text(Money.format(part.amount)).font(.llLabelBold).monospacedDigit()
                }
                .accessibilityElement(children: .combine)
            }
            RuleDivider()
            HStack(alignment: .firstTextBaseline) {
                Text(totalLabel).font(.llBodyBold)
                Spacer(minLength: Theme.Spacing.s)
                Text(Money.format(total)).font(.llBodyBold).monospacedDigit()
            }
            .accessibilityElement(children: .combine)
        }
    }
}

/// "Spending this month": segmented bar by area plus a legend.
private struct SpendingSummary: View {
    let spending: MoneyWidgetsViewState.Spending

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            HStack(alignment: .firstTextBaseline) {
                Text("Spending this month").font(.llBodyBold)
                Spacer()
                Text(L10n.tr("\(Money.format(spending.total)) in \(spending.monthText)")).font(.llLabelBold)
            }
            SpendingBar(categories: spending.categories)
            FlowRow(spacing: 14) {
                ForEach(spending.categories) { category in
                    HStack(spacing: 6) {
                        RoundedRectangle(cornerRadius: 3)
                            .fill((Area(rawValue: category.area) ?? .other).color)
                            .strokeBorder(Theme.Palette.ink, lineWidth: 2)
                            .frame(width: 10, height: 10)
                        Text(category.label).font(.llLabel)
                        Text(Money.format(category.amount)).font(.llLabelBold)
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }
}

/// One horizontal bar, one coloured part per category, sized by the API's `share`. Used on Money home and in details.
struct SpendingBar: View {
    let categories: [MoneyWidgetsViewState.Category]
    var height: CGFloat = 20

    var body: some View {
        GeometryReader { proxy in
            HStack(spacing: 0) {
                ForEach(categories) { category in
                    Rectangle()
                        .fill((Area(rawValue: category.area) ?? .other).color)
                        .frame(width: max(0, proxy.size.width * CGFloat(category.share)))
                        .overlay(alignment: .trailing) { Rectangle().fill(Theme.Palette.ink).frame(width: 2) }
                }
                Spacer(minLength: 0)
            }
        }
        .frame(height: height)
        .background(Theme.Palette.surface)
        .clipShape(HandCut.bar)
        .overlay(HandCut.bar.strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Spending by category")
        .accessibilityValue(categories.map { "\($0.label) \(Money.spoken($0.amount))" }.joined(separator: ", "))
    }
}

private struct BillsList: View {
    let bills: MoneyWidgetsViewState.Bills

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Text("Bills, next 30 days").font(.llBodyBold)
                Spacer()
                Text(Money.format(bills.totalNext30Days)).font(.llLabelBold)
            }
            .padding(.bottom, Theme.Spacing.xs)
            if bills.items.isEmpty {
                Text("No bills in the next 30 days.").font(.llBody).foregroundStyle(Theme.Palette.muted)
            }
            ForEach(Array(bills.items.enumerated()), id: \.element.id) { offset, bill in
                HStack(spacing: Theme.Spacing.m) {
                    Text(bill.shortDateText).font(.llLabel).foregroundStyle(Theme.Palette.muted).frame(width: 48, alignment: .leading)
                    Text(bill.name).font(.llBody).lineLimit(1).frame(maxWidth: .infinity, alignment: .leading)
                    if let chip = bill.priceRiseChip { Chip(text: chip, fill: Theme.Palette.health) }
                    Text(Money.format(bill.amount)).font(.llBodyBold)
                }
                .frame(minHeight: 40)
                .accessibilityElement(children: .combine)
                if offset < bills.items.count - 1 { RuleDivider() }
            }
        }
    }
}

private struct SubscriptionsList: View {
    let subscriptions: MoneyWidgetsViewState.Subscriptions

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .firstTextBaseline) {
                Text("Subscriptions").font(.llBodyBold)
                Spacer()
                Text(L10n.tr("\(Money.format(subscriptions.monthlyTotal)) a month · \(subscriptions.countText)"))
                    .font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
            .padding(.bottom, Theme.Spacing.xs)
            if subscriptions.items.isEmpty {
                Text("No subscriptions found.").font(.llBody).foregroundStyle(Theme.Palette.muted)
            }
            ForEach(Array(subscriptions.items.enumerated()), id: \.element.id) { offset, item in
                HStack(spacing: 10) {
                    LLIconImage(LLIcon.from(emoji: item.emoji, fallback: .subscriptions), size: 24)
                    Text(item.merchant).font(.llBody).frame(maxWidth: .infinity, alignment: .leading)
                    if let chip = item.priceRiseChip { Chip(text: chip, fill: Theme.Palette.health) }
                    Text(item.monthlyCostText).font(.llBodyBold).frame(minWidth: 64, alignment: .trailing)
                }
                .frame(minHeight: 40)
                .accessibilityElement(children: .combine)
                .accessibilityHint(item.priceRiseText ?? "")
                if offset < subscriptions.items.count - 1 { RuleDivider() }
            }
        }
    }
}

private struct BudgetsList: View {
    let budgets: MoneyWidgetsViewState.Budgets

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Budgets", icon: .budget).font(.llBodyBold)
            if budgets.items.isEmpty {
                Text("No budgets set.").font(.llBody).foregroundStyle(Theme.Palette.muted)
            }
            ForEach(budgets.items) { budget in
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    HStack {
                        Text(budget.label).font(.llLabelBold)
                        Text("· \(budget.statusText)").font(.llLabel)
                        Spacer()
                        Text(budget.detailText).font(.llLabel)
                    }
                    InkProgressBar(value: budget.progress, color: (Area(rawValue: budget.area) ?? .other).color, height: 14)
                }
                .accessibilityElement(children: .combine)
            }
        }
    }
}

private struct GoalsList: View {
    let goals: [MoneyWidgetsViewState.Goal]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label("Savings goals", icon: .goal).font(.llBodyBold)
            if goals.isEmpty {
                Text("No savings goals yet.").font(.llBody).foregroundStyle(Theme.Palette.muted)
            }
            ForEach(goals) { goal in
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    HStack {
                        Text(goal.name).font(.llLabelBold)
                        Spacer()
                        Text(goal.detailText).font(.llLabel)
                    }
                    InkProgressBar(value: goal.progress, color: Theme.Palette.money, height: 14)
                    if let plan = goal.planText {
                        Text(plan).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                }
                .accessibilityElement(children: .combine)
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") {
    ScrollView { MoneyWidgetsView(state: Fixtures.Widgets.ready).padding(20) }.paperBackground()
}

#Preview("Ready · dark") {
    ScrollView { MoneyWidgetsView(state: Fixtures.Widgets.ready).padding(20) }.paperBackground().previewDark()
}

#Preview("Ready · AX3") {
    ScrollView { MoneyWidgetsView(state: Fixtures.Widgets.ready).padding(20) }.paperBackground().previewLargeType()
}

#Preview("Partial error · light") {
    ScrollView { MoneyWidgetsView(state: Fixtures.Widgets.partialError).padding(20) }.paperBackground()
}

#Preview("Empty · light") {
    ScrollView { MoneyWidgetsView(state: Fixtures.Widgets.empty).padding(20) }.paperBackground()
}

#Preview("Loading · light") {
    ScrollView { MoneyWidgetsView(state: Fixtures.Widgets.loading).padding(20) }.paperBackground()
}
