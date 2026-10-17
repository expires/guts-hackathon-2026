// Draft by W6. Owned by the UI owner from creation.
import SwiftUI

/// Money tab widgets: balance and net worth, spending, subscriptions, bills, budgets and goals.
struct MoneyWidgetsView: View {
    let state: MoneyWidgetsViewState
    var actions: MoneyWidgetsActions = .noop

    var body: some View {
        VStack(spacing: Theme.Spacing.l) {
            WidgetCard(title: "Your money", section: state.overview, actions: actions) { overview in
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    line("Balance", Money.format(overview.balance), value: overview.balance, bold: true)
                    line("Net worth", Money.format(overview.netWorth), value: overview.netWorth)
                    ForEach(overview.accounts) { account in
                        line("\(account.name), \(account.kindLabel)", Money.format(account.balance), value: account.balance)
                            .font(.subheadline)
                    }
                    Text(overview.asOfText).font(.footnote).foregroundStyle(.secondary)
                }
            }
            WidgetCard(title: "Spending", section: state.spending, actions: actions) { spending in
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    line(spending.monthText, Money.format(spending.total), value: spending.total, bold: true)
                    ForEach(spending.categories) { category in
                        VStack(alignment: .leading, spacing: 2) {
                            line("\(category.emoji) \(category.label)", Money.format(category.amount), value: category.amount)
                            ProgressView(value: min(1, max(0, category.share)))
                                .accessibilityHidden(true)
                            if let change = category.changeText {
                                Text(change).font(.footnote).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
            WidgetCard(title: "Subscriptions", section: state.subscriptions, actions: actions) { subs in
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    line(subs.countText, FinanceMapping.pounds(subs.monthlyTotal) + " a month", value: subs.monthlyTotal, bold: true)
                    ForEach(subs.items) { item in
                        VStack(alignment: .leading, spacing: 2) {
                            line("\(item.emoji) \(item.merchant)", item.amountText, value: item.monthlyCost)
                            if let rise = item.priceRiseText {
                                Label(rise, systemImage: "arrow.up.right").font(.footnote).foregroundStyle(.orange)
                            }
                        }
                    }
                }
            }
            WidgetCard(title: "Coming up", section: state.bills, actions: actions) { bills in
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    line("Next 30 days", Money.format(bills.totalNext30Days), value: bills.totalNext30Days, bold: true)
                    ForEach(bills.items) { bill in
                        VStack(alignment: .leading, spacing: 2) {
                            line("\(bill.emoji) \(bill.name)", FinanceMapping.pounds(bill.amount), value: bill.amount)
                            Text("\(bill.dueText). \(bill.statusText)").font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            WidgetCard(title: "Budgets", section: state.budgets, actions: actions) { budgets in
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Text(budgets.monthText).font(.subheadline).foregroundStyle(.secondary)
                    ForEach(budgets.items) { item in
                        VStack(alignment: .leading, spacing: 2) {
                            line("\(item.emoji) \(item.label)", item.statusText, value: item.spent)
                            ProgressView(value: min(1, max(0, item.progress)))
                                .tint(item.status == .over ? .red : (item.status == .near ? .orange : .green))
                                .accessibilityHidden(true)
                            Text(item.detailText).font(.footnote).foregroundStyle(.secondary)
                        }
                    }
                }
            }
            WidgetCard(title: "Savings goals", section: state.goals, actions: actions) { goals in
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    ForEach(goals) { goal in
                        VStack(alignment: .leading, spacing: 2) {
                            line("\(goal.emoji) \(goal.name)", goal.detailText, value: goal.saved)
                            ProgressView(value: min(1, max(0, goal.progress))).accessibilityHidden(true)
                            if let plan = goal.planText { Text(plan).font(.footnote).foregroundStyle(.secondary) }
                        }
                    }
                }
            }
        }
    }

    private func line(_ label: String, _ text: String, value: Double, bold: Bool = false) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
            Spacer(minLength: Theme.Spacing.s)
            Text(text).monospacedDigit().contentTransition(.numericText(value: value))
        }
        .font(bold ? .headline : .body)
        .frame(minHeight: 28)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label), \(text)")
    }
}

private struct WidgetCard<Value: Equatable & Sendable, Content: View>: View {
    let title: String
    let section: WidgetSection<Value>
    let actions: MoneyWidgetsActions
    @ViewBuilder let content: (Value) -> Content

    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text(title).font(.headline)
                switch section.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    if let value = section.value { content(value) }
                    if let link = section.moveLink {
                        Button {
                            actions.onShowMove(link.moveID)
                        } label: {
                            Label(link.text, systemImage: "lightbulb")
                                .font(.footnote.weight(.medium))
                                .multilineTextAlignment(.leading)
                                .frame(minHeight: Theme.minTarget, alignment: .leading)
                        }
                    }
                }
            }
        }
        .accessibilityIdentifier("widget.\(title)")
    }
}

#Preview("Ready · light") { ScrollView { MoneyWidgetsView(state: Fixtures.Widgets.ready).padding() } }
#Preview("Ready · dark") { ScrollView { MoneyWidgetsView(state: Fixtures.Widgets.ready).padding() }.previewDark() }
#Preview("Ready · AX3") { ScrollView { MoneyWidgetsView(state: Fixtures.Widgets.ready).padding() }.previewLargeType() }
#Preview("Partial error · light") { ScrollView { MoneyWidgetsView(state: Fixtures.Widgets.partialError).padding() } }
#Preview("Loading · light") { ScrollView { MoneyWidgetsView(state: Fixtures.Widgets.loading).padding() } }
