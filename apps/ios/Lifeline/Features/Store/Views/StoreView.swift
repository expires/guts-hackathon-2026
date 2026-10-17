import SwiftUI

/// Paid extras. Every purchase is a demo payment. Lessons are always free.
struct StoreView: View {
    let state: StoreViewState
    var actions: StoreActions = .noop

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                    DemoPaymentLabel()
                    Text(state.lessonsNote).font(.subheadline).foregroundStyle(.secondary)
                    ForEach(state.products) { product in
                        GlassCard {
                            HStack(spacing: Theme.Spacing.m) {
                                Text(product.emoji).font(.largeTitle).accessibilityHidden(true)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(product.title).font(.headline)
                                    Text(product.detail).font(.subheadline).foregroundStyle(.secondary)
                                }
                                Spacer(minLength: 0)
                                if product.isOwned {
                                    Label("Owned", systemImage: "checkmark.seal.fill")
                                        .labelStyle(.iconOnly)
                                        .foregroundStyle(.green)
                                        .accessibilityLabel("Owned")
                                } else {
                                    Button { actions.onBuy(product.id) } label: {
                                        if product.isPurchasing { ProgressView() } else { Text(product.priceText) }
                                    }
                                    .buttonStyle(.glassProminent)
                                    .frame(minHeight: Theme.minTarget)
                                    .accessibilityLabel("Buy \(product.title). \(state.demoLabel)")
                                    .accessibilityIdentifier("store.buy.\(product.id)")
                                }
                            }
                        }
                    }
                    if let message = state.message {
                        Text(message).font(.subheadline).accessibilityIdentifier("store.message")
                    }
                }
                .padding(Theme.Spacing.l)
            }
            .navigationTitle("Extras")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done", action: actions.onClose)
                }
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Fresh · light") {
    StoreView(state: Fixtures.Store.fresh)
}

#Preview("Fresh · dark") {
    StoreView(state: Fixtures.Store.fresh).previewDark()
}

#Preview("Fresh · AX3") {
    StoreView(state: Fixtures.Store.fresh).previewLargeType()
}

#Preview("Purchasing · light") {
    StoreView(state: Fixtures.Store.purchasing)
}

#Preview("Purchasing · dark") {
    StoreView(state: Fixtures.Store.purchasing).previewDark()
}

#Preview("Purchasing · AX3") {
    StoreView(state: Fixtures.Store.purchasing).previewLargeType()
}

#Preview("Owned · light") {
    StoreView(state: Fixtures.Store.owned)
}

#Preview("Owned · dark") {
    StoreView(state: Fixtures.Store.owned).previewDark()
}

#Preview("Owned · AX3") {
    StoreView(state: Fixtures.Store.owned).previewLargeType()
}
