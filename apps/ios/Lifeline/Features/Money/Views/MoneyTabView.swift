import SwiftUI

/// Money tab: what you have, what you owe, and money actions.
struct MoneyTabView: View {
    let state: MoneyTabViewState
    var actions: ActionTabActions = .noop

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.l) {
                GlassCard {
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        row("Net worth", state.netWorth, bold: true)
                        row("Pay per year", state.annualIncome)
                        row("Costs per month", state.monthlyCosts)
                    }
                }
                GlassCard {
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        Text("You have").font(.headline)
                        ForEach(state.have) { row($0.label, $0.value) }
                    }
                }
                if !state.owe.isEmpty {
                    GlassCard {
                        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                            Text("You owe").font(.headline)
                            ForEach(state.owe) { row($0.label, $0.value) }
                            if let note = state.mortgageNote {
                                Text(note).font(.footnote).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
                if let outcome = state.outcome {
                    OutcomeBanner(outcome: outcome, onDismiss: actions.onDismissOutcome)
                }
                SectionTitle(text: "What to do")
                ActionList(actions: state.actions, isBusy: state.isBusy, onAction: actions.onAction)
            }
            .padding(Theme.Spacing.l)
        }
        .navigationTitle("Money")
    }

    private func row(_ label: String, _ value: Double, bold: Bool = false) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(Money.format(value))
                .monospacedDigit()
                .foregroundStyle(value < 0 ? .red : .primary)
                .contentTransition(.numericText(value: value))
        }
        .font(bold ? .headline : .body)
        .frame(minHeight: 32)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label), \(Money.spoken(value))")
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
