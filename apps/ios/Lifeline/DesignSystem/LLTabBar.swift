import SwiftUI

/// Tab bar from the handoff, compact (ADR 0048): surface, ink top rule, 4 equal columns, 22 pt icons
/// (white fill inactive, colour fill active), 11 pt labels (bold when active), 44 pt targets.
struct LLTabBar: View {
    struct Item: Identifiable, Equatable {
        var id: String
        var title: String
        var icon: LLIcon
    }

    let items: [Item]
    let selection: String
    let onSelect: (String) -> Void

    var body: some View {
        HStack(spacing: 0) {
            ForEach(items) { item in
                let isActive = item.id == selection
                Button { onSelect(item.id) } label: {
                    VStack(spacing: 2) {
                        LLIconImage(item.icon, size: 22, active: isActive)
                        Text(item.title)
                            .font(.custom(isActive ? LLFont.bodyBold : LLFont.body, size: 11, relativeTo: .caption2))
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                    }
                    .foregroundStyle(Theme.Palette.ink)
                    .frame(maxWidth: .infinity, minHeight: 44)
                    .contentShape(.rect)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(item.title)
                .accessibilityAddTraits(isActive ? [.isSelected, .isButton] : .isButton)
                .accessibilityIdentifier("tab.\(item.id)")
            }
        }
        .padding(.top, Theme.Spacing.xs)
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
        .init(id: "money", title: "Money", icon: .tabMoney), .init(id: "penny", title: "Penny", icon: .pennySmiling),
        .init(id: "play", title: "Play", icon: .tabPlay), .init(id: "you", title: "You", icon: .tabYou),
    ], selection: "money") { _ in } }.paperBackground()
}

#Preview("Tab bar · dark") {
    VStack { Spacer(); LLTabBar(items: [
        .init(id: "money", title: "Money", icon: .tabMoney), .init(id: "penny", title: "Penny", icon: .pennySmiling),
        .init(id: "play", title: "Play", icon: .tabPlay), .init(id: "you", title: "You", icon: .tabYou),
    ], selection: "penny") { _ in } }.paperBackground().previewDark()
}
