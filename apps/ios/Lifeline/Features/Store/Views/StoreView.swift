// Rebuilt for ADR 0026 (You-Paywall.dc.html) by W7.
import SwiftUI

/// Penny Plus paywall. Demo only: every price is a "Demo payment" and no real money is taken.
struct StoreView: View {
    let state: StoreViewState
    var actions: StoreActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                HStack {
                    Spacer()
                    HeaderSquareButton(kind: .close, identifier: "store.close", action: actions.onClose)
                }
                HStack(spacing: Theme.Spacing.l) {
                    LLIconImage(.lock, size: 64)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(Brand.productName) Plus").llEyebrow()
                        Text("Play every life").font(.llTitle).accessibilityAddTraits(.isHeader)
                    }
                }
                VStack(spacing: Theme.Spacing.s) {
                    ForEach(Array(state.products.enumerated()), id: \.element.id) { offset, product in
                        option(product, shape: [HandCut.card, .cardAlt, HandCut((18, 24, 16, 22), (22, 16, 24, 18))][offset % 3])
                    }
                }
                .accessibilityElement(children: .contain)
                .accessibilityLabel("Extras")

                HStack(spacing: Theme.Spacing.m) {
                    LLIconImage(.demoPay, size: 32)
                    VStack(alignment: .leading, spacing: 0) {
                        Text(state.demoLabel).font(.llBodyBold)
                        Text("Hackathon demo. No real money is taken.").font(.llLabel)
                    }
                }
                .padding(Theme.Spacing.m)
                .frame(maxWidth: .infinity, alignment: .leading)
                .inkSurface(.badge, fill: Theme.Palette.family, lineWidth: Theme.chipOutline)
                .foregroundStyle(Theme.Palette.onArea)
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("demoPaymentLabel")

                Text(state.lessonsNote).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                if let message = state.message {
                    Text(message).font(.llBodyBold).accessibilityIdentifier("store.message")
                }
                VStack(spacing: Theme.Spacing.s) {
                    Button { if let id = state.selectedID { actions.onBuy(id) } } label: {
                        HStack(spacing: 10) {
                            if state.selected?.isPurchasing == true {
                                ProgressView().tint(Theme.Palette.surface)
                            }
                            Text(state.buyTitle).lineLimit(1).minimumScaleFactor(0.6)
                        }
                    }
                    .buttonStyle(.main)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .disabled(!state.canBuy)
                    .accessibilityLabel("\(state.buyTitle). \(state.demoLabel)")
                    .accessibilityIdentifier("store.buy.\(state.selectedID ?? "none")")
                    Button("Restore a demo purchase", action: actions.onRestore)
                        .buttonStyle(.text)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .frame(maxWidth: .infinity)
                        .accessibilityIdentifier("store.restore")
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    private func option(_ product: StoreViewState.Product, shape: HandCut) -> some View {
        let isOn = product.id == state.selectedID
        return Button { actions.onSelect(product.id) } label: {
            HStack(spacing: Theme.Spacing.m) {
                Circle()
                    .fill(isOn ? Theme.Palette.ink : Theme.Palette.surface)
                    .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: 3))
                    .overlay(Circle().fill(Theme.Palette.surface).frame(width: 8, height: 8).opacity(isOn ? 1 : 0))
                    .frame(width: 24, height: 24)
                LLIconImage(LLIcon(rawValue: product.icon) ?? .demoPay, size: 32)
                VStack(alignment: .leading, spacing: 2) {
                    Text(product.title).font(.llBodyBold)
                    Text(product.detail).font(.llLabel).fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                VStack(alignment: .trailing, spacing: 2) {
                    Text(product.priceText).font(.llBodyBold).lineLimit(1)
                    if product.isOwned {
                        Chip(text: "Owned", fill: Theme.Palette.money)
                    } else {
                        Text(state.demoLabel).font(.llLabel).lineLimit(1)
                    }
                }
            }
            // Selected: opaque area fill with `onArea` text, so it reads in light and dark (V4 fix).
            .foregroundStyle(isOn ? Theme.Palette.onArea : Theme.Palette.ink)
            .padding(Theme.Spacing.m)
            .frame(minHeight: Theme.minTarget)
            .inkSurface(shape, fill: isOn ? Theme.Palette.home : Theme.Palette.surface, hero: isOn)
            .contentShape(shape)
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isOn ? [.isSelected] : [])
        .accessibilityLabel("\(product.title), \(product.priceText), \(state.demoLabel). \(product.detail)\(product.isOwned ? ". Owned" : "")")
        .accessibilityIdentifier("store.option.\(product.id)")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Fresh · light") { StoreView(state: Fixtures.Store.fresh) }
#Preview("Fresh · dark") { StoreView(state: Fixtures.Store.fresh).previewDark() }
#Preview("Fresh · AX3") { StoreView(state: Fixtures.Store.fresh).previewLargeType() }
#Preview("God Mode selected · light") { StoreView(state: StoreFixtures.godModeSelected) }
#Preview("Purchasing · light") { StoreView(state: Fixtures.Store.purchasing) }
#Preview("Owned · light") { StoreView(state: Fixtures.Store.owned) }
#Preview("Owned · dark") { StoreView(state: Fixtures.Store.owned).previewDark() }
