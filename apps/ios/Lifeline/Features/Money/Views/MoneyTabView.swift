import SwiftUI

/// Money tab: what you have, what you owe, and money actions.
struct MoneyTabView: View {
    let state: MoneyTabViewState
    var actions: ActionTabActions = .noop

    var body: some View {
        SheetContainer(title: "Finances", closeIdentifier: "menu.close", onClose: actions.onClose) {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Net worth").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    Text(Money.format(state.netWorth)).font(.llHero).contentTransition(.numericText(value: state.netWorth))
                }
                Spacer()
            }
            RowGroup(title: L10n.tr("Money I keep")) {
                ForEach(state.have) { row in
                    ListRow(icon: icon(for: row.id), title: row.label, trailing: Money.format(row.value), showsChevron: false)
                }
            }
            if !state.owe.isEmpty {
                RowGroup(title: L10n.tr("Money I owe"), shape: .cardAlt) {
                    ForEach(state.owe) { row in
                        ListRow(icon: icon(for: row.id), title: row.label, subtitle: row.id == "mortgage" ? state.mortgageNote : nil, trailing: Money.format(row.value), showsChevron: false)
                    }
                }
            }
            RowGroup(title: L10n.tr("Every year")) {
                ListRow(icon: .payRise, title: L10n.tr("Pay per year"), trailing: Money.format(state.annualIncome), showsChevron: false)
                ListRow(icon: .bills, title: L10n.tr("Costs per month"), trailing: Money.format(state.monthlyCosts), showsChevron: false)
            }
            RowGroupTitle(text: L10n.tr("What you can do"))
            ActionList(actions: state.actions, isBusy: state.isBusy, onAction: actions.onAction, emptyText: L10n.tr("Nothing to do here this year."))
        }
    }

    private func icon(for id: String) -> LLIcon {
        switch id {
        case "home": .home
        case "mortgage": .bank
        case "debt": .card
        case "studentLoan": .study
        case "pension": .pension
        case "investments", "crypto": .investment
        default: .savings
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Mid-life · light") {
    MoneyTabView(state: Fixtures.Tabs.money).previewInNavigation()
}

#Preview("Mid-life · dark") {
    MoneyTabView(state: Fixtures.Tabs.money).previewInNavigation().previewDark()
}

#Preview("Mid-life · AX3") {
    MoneyTabView(state: Fixtures.Tabs.money).previewInNavigation().previewLargeType()
}

#Preview("New life · light") {
    MoneyTabView(state: Fixtures.Tabs.moneyNewLife).previewInNavigation()
}

#Preview("New life · dark") {
    MoneyTabView(state: Fixtures.Tabs.moneyNewLife).previewInNavigation().previewDark()
}

#Preview("New life · AX3") {
    MoneyTabView(state: Fixtures.Tabs.moneyNewLife).previewInNavigation().previewLargeType()
}
