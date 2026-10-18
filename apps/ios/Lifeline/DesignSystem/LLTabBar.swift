import SwiftUI

/// Floating tab bar (PENNY_V3_BUILD.md G2, canvas): one app-wide bar for Money, Penny, Play and You.
/// A white card with the ink outline and hard shadow, 16 pt from the sides, 28 pt icons and 13 pt labels;
/// the active tab sits on a soft green pill. No glass effect. RootScreen places it with `.safeAreaInset`,
/// so every scrolling screen gets bottom padding and the last item is never hidden behind it.
struct LLTabBar: View {
    struct Item: Identifiable, Equatable {
        var id: String
        var title: String
        var icon: LLIcon
    }

    let items: [Item]
    let selection: String
    let onSelect: (String) -> Void

    /// Height of the bar itself, without its outer padding.
    static let height: CGFloat = 72

    var body: some View {
        HStack(spacing: 0) {
            ForEach(items) { item in
                let isActive = item.id == selection
                Button { onSelect(item.id) } label: {
                    VStack(spacing: 2) {
                        LLIconImage(item.icon, size: 28, active: isActive)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 2)
                            .background {
                                if isActive { Capsule().fill(Theme.Palette.money.opacity(0.25)) }
                            }
                        Text(item.title)
                            .font(.custom(isActive ? LLFont.bodyBold : LLFont.body, size: 13, relativeTo: .caption))
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
        .padding(.horizontal, Theme.Spacing.s)
        .frame(height: Self.height)
        .background {
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(Theme.Palette.ink)
                .offset(y: 5)
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(Theme.Palette.surface)
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline)
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.top, Theme.Spacing.s)
        .padding(.bottom, Theme.Spacing.s)
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
