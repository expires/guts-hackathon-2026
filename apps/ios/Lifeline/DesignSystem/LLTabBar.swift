import SwiftUI

/// Tab bar from the handoff: surface, 3 pt ink top rule, 4 equal columns, 28 pt icons
/// (white fill inactive, colour fill active), 13 pt labels (bold when active).
struct LLTabBar: View {
    struct Item: Identifiable, Equatable {
        var id: String
        var title: String
        var icon: LLIcon
        /// SF Symbol used instead of `icon` when set (for tabs with no drawn icon yet).
        var symbol: String?
    }

    let items: [Item]
    let selection: String
    let onSelect: (String) -> Void

    var body: some View {
        HStack(spacing: 0) {
            ForEach(items) { item in
                let isActive = item.id == selection
                Button { onSelect(item.id) } label: {
                    VStack(spacing: Theme.Spacing.xs) {
                        if let symbol = item.symbol {
                            Image(systemName: isActive ? symbol + ".fill" : symbol)
                                .font(.system(size: 22, weight: .semibold))
                                .frame(width: 28, height: 28)
                                .accessibilityHidden(true)
                        } else {
                            LLIconImage(item.icon, size: 28, active: isActive)
                        }
                        Text(item.title)
                            .font(isActive ? .llLabelBold : .llLabel)
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                    }
                    .foregroundStyle(Theme.Palette.ink)
                    .frame(maxWidth: .infinity, minHeight: 56)
                    .contentShape(.rect)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(item.title)
                .accessibilityAddTraits(isActive ? [.isSelected, .isButton] : .isButton)
                .accessibilityIdentifier("tab.\(item.id)")
            }
        }
        .padding(.top, Theme.Spacing.s)
        .background {
            Theme.Palette.surface
                .ignoresSafeArea(edges: .bottom)
                .overlay(alignment: .top) { Rectangle().fill(Theme.Palette.ink).frame(height: Theme.outline) }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("tabBar")
    }
}

#Preview("Tab bar · light") {
    VStack { Spacer(); LLTabBar(items: [
        .init(id: "money", title: "Money", icon: .tabMoney), .init(id: "life", title: "Life", icon: .tabLife),
        .init(id: "play", title: "Play", icon: .tabPlay), .init(id: "you", title: "You", icon: .tabYou),
    ], selection: "money") { _ in } }.paperBackground()
}

#Preview("Tab bar · dark") {
    VStack { Spacer(); LLTabBar(items: [
        .init(id: "money", title: "Money", icon: .tabMoney), .init(id: "life", title: "Life", icon: .tabLife),
        .init(id: "play", title: "Play", icon: .tabPlay), .init(id: "you", title: "You", icon: .tabYou),
    ], selection: "life") { _ in } }.paperBackground().previewDark()
}
