import SwiftUI

/// Rows for `available_actions`, inside one card with rule dividers. Paid actions show "Demo payment".
struct ActionList: View {
    let actions: [ActionItemState]
    let isBusy: Bool
    let onAction: (String) -> Void
    var emptyText = "Nothing to do here right now. Tap AGE to move on."

    var body: some View {
        if actions.isEmpty {
            Text(emptyText)
                .font(.llBody)
                .foregroundStyle(Theme.Palette.muted)
                .frame(maxWidth: .infinity, alignment: .leading)
        } else {
            VStack(spacing: 0) {
                ForEach(Array(actions.enumerated()), id: \.element.id) { offset, item in
                    if offset > 0 { RuleDivider() }
                    Button { onAction(item.id) } label: {
                        HStack(spacing: Theme.Spacing.m) {
                            LLIconImage(LLIcon.from(emoji: item.emoji), size: 32)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(item.label).font(.llBodyBold)
                                if let hint = item.hint {
                                    Text(hint).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                }
                            }
                            Spacer(minLength: 0)
                            if item.isPaid {
                                Chip(text: Brand.demoPaymentLabel, fill: Theme.Palette.family)
                            }
                            Chevron()
                        }
                        .foregroundStyle(Theme.Palette.ink)
                        .padding(.horizontal, Theme.Spacing.l)
                        .padding(.vertical, Theme.Spacing.m)
                        .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
                        .contentShape(.rect)
                    }
                    .buttonStyle(.plain)
                    .disabled(!item.isEnabled || isBusy)
                    .opacity(item.isEnabled ? 1 : 0.45)
                    .accessibilityLabel([item.label, item.hint, item.isPaid ? Brand.demoPaymentLabel : nil].compactMap { $0 }.joined(separator: ". "))
                    .accessibilityIdentifier("action.\(item.id)")
                }
            }
            .inkSurface(.card)
        }
    }
}

/// Section title used on tab screens (24, Bricolage).
struct SectionTitle: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.llTitle)
            .foregroundStyle(Theme.Palette.ink)
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityAddTraits(.isHeader)
    }
}
