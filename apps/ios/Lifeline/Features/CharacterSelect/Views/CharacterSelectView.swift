import SwiftUI

/// Pick a life. Order: Play yourself, presets, Random, God Mode.
struct CharacterSelectView: View {
    let state: CharacterSelectViewState
    var actions: CharacterSelectActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                if state.usesSampleData {
                    DemoDataBadge()
                }
                Text(state.intro)
                    .font(.body)
                    .foregroundStyle(.secondary)

                GlassEffectContainer(spacing: Theme.Spacing.m) {
                    VStack(spacing: Theme.Spacing.m) {
                        ForEach(state.cards) { card in
                            CharacterCard(card: card) { actions.onSelect(card.id) }
                        }
                    }
                }

                switch state.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    EmptyView()
                }

                Text(state.versionText)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                    .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                    .contentShape(.rect)
                    .onLongPressGesture(perform: actions.onVersionLongPress)
                    .accessibilityIdentifier("app.version")
            }
            .padding(Theme.Spacing.l)
        }
        .navigationTitle("Choose a life")
        .toolbar {
            ToolbarItemGroup(placement: .topBarTrailing) {
                Menu("More", systemImage: "ellipsis.circle") {
                    Button("Play with friends", systemImage: "person.3", action: actions.onOpenRooms)
                    Button("Extras (\(Brand.demoPaymentLabel))", systemImage: "bag", action: actions.onOpenStore)
                    Button("Where our data comes from", systemImage: "chart.bar.doc.horizontal", action: actions.onOpenSources)
                }
                .accessibilityIdentifier("characterSelect.more")
            }
        }
    }
}

/// One tappable life card.
struct CharacterCard: View {
    let card: CharacterSelectViewState.Card
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .center, spacing: Theme.Spacing.l) {
                Text(card.emoji)
                    .font(.system(size: 44))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    HStack(spacing: Theme.Spacing.s) {
                        Text(card.title).font(.headline)
                        if let badge = card.badge {
                            Text(badge)
                                .font(.caption2.weight(.semibold))
                                .padding(.horizontal, Theme.Spacing.s)
                                .padding(.vertical, 2)
                                .background(.tint.opacity(0.15), in: .capsule)
                        }
                    }
                    Text(card.subtitle)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.leading)
                    if let detail = card.detail {
                        Text(detail).font(.footnote.monospacedDigit())
                    }
                }
                Spacer(minLength: 0)
                Image(systemName: card.isLocked ? "lock.fill" : "chevron.right")
                    .foregroundStyle(.secondary)
                    .accessibilityHidden(true)
            }
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .padding(.vertical, Theme.Spacing.s)
            .contentShape(.rect)
        }
        .buttonStyle(.glass)
        .accessibilityLabel([card.title, card.subtitle, card.detail, card.badge, card.isLocked ? "Locked" : nil].compactMap { $0 }.joined(separator: ". "))
        .accessibilityIdentifier("character.\(card.id)")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") {
    CharacterSelectView(state: Fixtures.CharacterSelect.ready).previewInNavigation()
}

#Preview("Ready · dark") {
    CharacterSelectView(state: Fixtures.CharacterSelect.ready).previewInNavigation().previewDark()
}

#Preview("Ready · AX3") {
    CharacterSelectView(state: Fixtures.CharacterSelect.ready).previewInNavigation().previewLargeType()
}

#Preview("God Mode owned · light") {
    CharacterSelectView(state: Fixtures.CharacterSelect.godModeOwned).previewInNavigation()
}

#Preview("God Mode owned · dark") {
    CharacterSelectView(state: Fixtures.CharacterSelect.godModeOwned).previewInNavigation().previewDark()
}

#Preview("God Mode owned · AX3") {
    CharacterSelectView(state: Fixtures.CharacterSelect.godModeOwned).previewInNavigation().previewLargeType()
}

#Preview("Loading · light") {
    CharacterSelectView(state: Fixtures.CharacterSelect.loading).previewInNavigation()
}

#Preview("Loading · dark") {
    CharacterSelectView(state: Fixtures.CharacterSelect.loading).previewInNavigation().previewDark()
}

#Preview("Loading · AX3") {
    CharacterSelectView(state: Fixtures.CharacterSelect.loading).previewInNavigation().previewLargeType()
}

#Preview("Offline · light") {
    CharacterSelectView(state: Fixtures.CharacterSelect.offline).previewInNavigation()
}

#Preview("Offline · dark") {
    CharacterSelectView(state: Fixtures.CharacterSelect.offline).previewInNavigation().previewDark()
}

#Preview("Offline · AX3") {
    CharacterSelectView(state: Fixtures.CharacterSelect.offline).previewInNavigation().previewLargeType()
}
