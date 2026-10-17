// Draft by W6. Owned by the UI owner from creation.
import SwiftUI

/// Action menus inside the Life tab (ADR 0016): Job, Assets, People, Money, Activities.
/// The glue attaches it under `LifeView` with `.safeAreaInset(edge: .bottom)`.
struct LifeMenuBarView: View {
    let state: LifeMenuViewState
    var actions: LifeMenuActions = .noop

    var body: some View {
        HStack(spacing: Theme.Spacing.xs) {
                ForEach(state.items) { item in
                    Button { actions.onOpen(item.menu) } label: {
                        VStack(spacing: 2) {
                            LLIconImage(item.icon, size: 24)
                            Text(item.title).font(.llLabel).lineLimit(1).minimumScaleFactor(0.7)
                        }
                        .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                        .overlay(alignment: .topTrailing) {
                            if item.count > 0 {
                                Text("\(item.count)")
                                    .font(.llLabelBold)
                                    .padding(.horizontal, 5)
                                    .background(Theme.Palette.ink, in: .capsule)
                                    .foregroundStyle(Theme.Palette.surface)
                                    .accessibilityHidden(true)
                            }
                        }
                    }
                    .buttonStyle(.second)
                    .disabled(!state.isEnabled)
                    .accessibilityLabel(item.title)
                    .accessibilityValue(item.count == 1 ? "1 action" : "\(item.count) actions")
                    .accessibilityIdentifier("lifeMenu.\(item.menu.rawValue)")
                }
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, Theme.Spacing.s)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Mid-life · light") { LifeMenuBarView(state: Fixtures.LifeMenu.midLife) }
#Preview("Mid-life · dark") { LifeMenuBarView(state: Fixtures.LifeMenu.midLife).previewDark() }
#Preview("Mid-life · AX3") { LifeMenuBarView(state: Fixtures.LifeMenu.midLife).previewLargeType() }
#Preview("Dead · light") { LifeMenuBarView(state: Fixtures.LifeMenu.dead) }
