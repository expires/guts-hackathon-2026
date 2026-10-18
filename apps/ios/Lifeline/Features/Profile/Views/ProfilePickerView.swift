import SwiftUI

/// "Who are you playing as?": You with your real data, and the sample students. The active one is marked.
struct ProfilePickerView: View {
    let state: ProfilePickerViewState
    var actions: ProfilePickerActions = .noop

    var body: some View {
        VStack(spacing: 0) {
            ScreenHeader(title: L10n.tr("Who are you playing as?"), leading: HeaderSquareButton(kind: .close, identifier: "picker.close", action: actions.onClose))
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.top, Theme.Spacing.s)
                .padding(.bottom, Theme.Spacing.xs)
            switch state.phase {
            case .loading:
                ScrollView { SkeletonList(rows: 4).padding(Theme.Spacing.margin) }
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                ScrollView {
                    VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                        Text("Play as you, or try a sample student to see how it works.")
                            .font(.llBody).fixedSize(horizontal: false, vertical: true)
                        if let message = state.errorMessage {
                            Text(message)
                                .font(.llBody).foregroundStyle(Theme.Palette.onArea)
                                .padding(Theme.Spacing.l)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .inkSurface(.cardAlt, fill: Theme.Palette.health)
                                .onTapGesture(perform: actions.onDismissError)
                                .accessibilityIdentifier("picker.error")
                        }
                        ForEach(state.cards) { card in
                            ProfileCard(card: card, isBusy: state.busyID == card.id, isDisabled: state.busyID != nil) {
                                actions.onPick(card.id)
                            }
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.margin)
                    .padding(.top, Theme.Spacing.s)
                    .padding(.bottom, Theme.Spacing.xl)
                }
                .scrollIndicators(.hidden)
            }
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }
}

private struct ProfileCard: View {
    let card: ProfilePickerViewState.Card
    let isBusy: Bool
    let isDisabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.m) {
                LLIconImage(icon, size: 48)
                    .frame(width: 64, height: 64)
                    .inkSurface(.badge, fill: card.isYou ? Theme.Palette.money : Theme.Palette.surface)
                VStack(alignment: .leading, spacing: 2) {
                    Text(card.title).font(.llBodyBold)
                    Text(card.subtitle).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    if let detail = card.detail, !detail.isEmpty {
                        Text(detail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                    HStack(spacing: Theme.Spacing.xs) {
                        if card.isActive { Chip(text: L10n.tr("Active"), fill: Theme.Palette.money) }
                        if let badge = card.badge { Chip(text: badge) }
                        if card.isTeam { Chip(text: L10n.tr("Team")) }
                    }
                    .padding(.top, 2)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if isBusy { ProgressView() } else { Chevron() }
            }
            .padding(Theme.Spacing.l)
            .frame(maxWidth: .infinity, minHeight: 88, alignment: .leading)
            .inkSurface(card.isYou ? .hero : .card, hero: card.isYou)
            .foregroundStyle(Theme.Palette.ink)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .disabled(isDisabled)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityLabel([card.title, card.subtitle, card.isActive ? L10n.tr("Active") : nil, card.badge].compactMap { $0 }.joined(separator: ". "))
        .accessibilityIdentifier("picker.card.\(card.id)")
    }

    private var icon: LLIcon {
        if card.isYou { return .tabYou }
        return card.avatar.flatMap(LLIcon.init(rawValue:)) ?? .study
    }
}

#Preview("Nothing active · light") { ProfilePickerView(state: ProfilePickerPreviews.nothingActive) }
#Preview("Sample active · light") { ProfilePickerView(state: ProfilePickerPreviews.sampleActive) }
#Preview("You active · dark") { ProfilePickerView(state: ProfilePickerPreviews.youActive).previewDark() }
#Preview("Importing · AX3") { ProfilePickerView(state: ProfilePickerPreviews.importing).previewLargeType() }
#Preview("Loading · light") { ProfilePickerView(state: ProfilePickerViewState()) }
