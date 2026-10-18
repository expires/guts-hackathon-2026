import SwiftUI

/// Pick a life. Order: Play yourself, presets, Random.
struct CharacterSelectView: View {
    let state: CharacterSelectViewState
    var actions: CharacterSelectActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(
                    title: L10n.tr("Choose a life"),
                    leading: actions.onClose.map { close in HeaderSquareButton(kind: .back, identifier: "characterSelect.back", action: close) }
                ) {
                }
                Text(state.intro).font(.llBody).foregroundStyle(Theme.Palette.muted)
                VStack(spacing: Theme.Spacing.m) {
                    ForEach(state.cards) { card in
                        CharacterCard(card: card) { actions.onSelect(card.id) }
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
                FlowRow(spacing: Theme.Spacing.s) {
                    Button("Play with friends", action: actions.onOpenRooms).buttonStyle(.text)
                        .accessibilityIdentifier("characterSelect.rooms")
                    Button("Data sources", action: actions.onOpenSources).buttonStyle(.text)
                        .accessibilityIdentifier("characterSelect.sources")
                }
                Text(state.versionText)
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                    .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                    .contentShape(.rect)
                    .onLongPressGesture(perform: actions.onVersionLongPress)
                    .accessibilityAction(named: "Debug menu", actions.onVersionLongPress)
                    .accessibilityIdentifier("app.version")
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s).padding(.bottom, Theme.Spacing.m)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }
}

/// One tappable life card.
struct CharacterCard: View {
    let card: CharacterSelectViewState.Card
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .center, spacing: Theme.Spacing.l) {
                LLIconImage(LLIcon.face(emoji: card.emoji), size: 48)
                    .font(.system(size: 44))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    ViewThatFits(in: .horizontal) {
                        HStack(spacing: Theme.Spacing.s) {
                            Text(card.title).font(.llBodyBold)
                            if let badge = card.badge { Chip(text: badge, fill: Theme.Palette.money) }
                        }
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            Text(card.title).font(.llBodyBold)
                            if let badge = card.badge { Chip(text: badge, fill: Theme.Palette.money) }
                        }
                    }
                    Text(card.subtitle)
                        .font(.llBody)
                        .foregroundStyle(Theme.Palette.muted)
                        .multilineTextAlignment(.leading)
                    if let detail = card.detail {
                        Text(detail).font(.llLabelBold)
                    }
                }
                Spacer(minLength: 0)
                Group {
                    if card.isLocked { LLIconImage(.lock) } else { Chevron() }
                }
                .accessibilityHidden(true)
            }
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .padding(Theme.Spacing.l)
            .foregroundStyle(Theme.Palette.ink)
            .inkSurface(card.kind == .playYourself ? .hero : .card, hero: card.kind == .playYourself)
        }
        .buttonStyle(.plain)
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
