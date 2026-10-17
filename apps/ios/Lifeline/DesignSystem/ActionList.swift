import SwiftUI

/// Buttons for `available_actions`. Paid actions show the "Demo payment" label.
struct ActionList: View {
    let actions: [ActionItemState]
    let isBusy: Bool
    let onAction: (String) -> Void
    var emptyText = "Nothing to do here right now. Tap AGE to move on."

    var body: some View {
        if actions.isEmpty {
            Text(emptyText)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity, alignment: .leading)
        } else {
            GlassEffectContainer(spacing: Theme.Spacing.s) {
                VStack(spacing: Theme.Spacing.s) {
                    ForEach(actions) { item in
                        Button { onAction(item.id) } label: {
                            HStack(spacing: Theme.Spacing.m) {
                                Text(item.emoji).font(.title2).accessibilityHidden(true)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(item.label).font(.headline)
                                    if let hint = item.hint {
                                        Text(hint).font(.subheadline).foregroundStyle(.secondary)
                                    }
                                }
                                Spacer(minLength: 0)
                                if item.isPaid {
                                    Text(Brand.demoPaymentLabel)
                                        .font(.caption2.weight(.semibold))
                                        .padding(.horizontal, Theme.Spacing.s)
                                        .padding(.vertical, 2)
                                        .background(.purple.opacity(0.15), in: .capsule)
                                }
                            }
                            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
                            .contentShape(.rect)
                        }
                        .buttonStyle(.glass)
                        .disabled(!item.isEnabled || isBusy)
                        .accessibilityLabel([item.label, item.hint, item.isPaid ? Brand.demoPaymentLabel : nil].compactMap { $0 }.joined(separator: ". "))
                        .accessibilityIdentifier("action.\(item.id)")
                    }
                }
            }
        }
    }
}

/// Section title used on tab screens.
struct SectionTitle: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.title3.bold())
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityAddTraits(.isHeader)
    }
}
