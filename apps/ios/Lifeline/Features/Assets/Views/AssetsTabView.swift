import SwiftUI

/// Assets tab: what you own and asset actions.
struct AssetsTabView: View {
    let state: AssetsTabViewState
    var actions: ActionTabActions = .noop

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.l) {
                GlassCard {
                    VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                        HStack {
                            Text("Total").font(.headline)
                            Spacer()
                            Text(Money.format(state.totalValue))
                                .font(.headline.monospacedDigit())
                                .contentTransition(.numericText(value: state.totalValue))
                        }
                        if state.items.isEmpty {
                            Text("You do not own anything yet.").foregroundStyle(.secondary)
                        }
                        ForEach(state.items) { item in
                            HStack {
                                Text(item.emoji).accessibilityHidden(true)
                                VStack(alignment: .leading) {
                                    Text(item.name)
                                    Text(item.kindLabel).font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(Money.format(item.value)).monospacedDigit()
                            }
                            .frame(minHeight: Theme.minTarget)
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel("\(item.name), \(item.kindLabel), \(Money.spoken(item.value))")
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
        .navigationTitle("Assets")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Mid-life · light") {
    AssetsTabView(state: Fixtures.Tabs.assets).previewInNavigation()
}

#Preview("Mid-life · dark") {
    AssetsTabView(state: Fixtures.Tabs.assets).previewInNavigation().previewDark()
}

#Preview("Mid-life · AX3") {
    AssetsTabView(state: Fixtures.Tabs.assets).previewInNavigation().previewLargeType()
}

#Preview("Empty · light") {
    AssetsTabView(state: Fixtures.Tabs.assetsEmpty).previewInNavigation()
}

#Preview("Empty · dark") {
    AssetsTabView(state: Fixtures.Tabs.assetsEmpty).previewInNavigation().previewDark()
}

#Preview("Empty · AX3") {
    AssetsTabView(state: Fixtures.Tabs.assetsEmpty).previewInNavigation().previewLargeType()
}
