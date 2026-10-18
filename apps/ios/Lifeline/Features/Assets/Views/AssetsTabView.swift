import SwiftUI

/// Assets tab: what you own and asset actions.
struct AssetsTabView: View {
    let state: AssetsTabViewState
    var actions: ActionTabActions = .noop

    var body: some View {
        SheetContainer(title: "Assets", closeIdentifier: "menu.close", onClose: actions.onClose) {
            RowGroup(title: L10n.tr("Things I own")) {
                if state.items.isEmpty {
                    ListRow(icon: .home, title: L10n.tr("Nothing yet"), subtitle: L10n.tr("Buy something below"), showsChevron: false)
                }
                ForEach(state.items) { item in
                    ListRow(icon: LLIcon.from(emoji: item.emoji, fallback: item.kindLabel.lowercased().contains("home") ? .home : .savings), title: item.name, subtitle: item.kindLabel, trailing: Money.format(item.value), showsChevron: false)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(L10n.tr("\(item.name), \(item.kindLabel), \(Money.spoken(item.value))"))
                }
            }
            HStack {
                Text("Total").font(.llBodyBold)
                Spacer()
                Text(Money.format(state.totalValue)).font(.llTitle).contentTransition(.numericText(value: state.totalValue))
            }
            RowGroupTitle(text: L10n.tr("What you can do"))
            ActionList(actions: state.actions, isBusy: state.isBusy, onAction: actions.onAction, emptyText: L10n.tr("Nothing to do here this year."))
        }
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
