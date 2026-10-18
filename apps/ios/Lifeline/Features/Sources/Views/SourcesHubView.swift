import SwiftUI

// Draft by W7 (ADR 0073). Owned by the UI owner from creation.

/// "Where Penny's data comes from" (ADR 0073): the server's summary, then one ink-outline card per source with
/// its status, update time, what it gives Penny and the screens that use it. A tap opens the detail.
struct SourcesHubView: View {
    let state: SourcesHubViewState
    var actions: SourcesHubActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                ForecastScreenHeader(title: L10n.tr("Where Penny's data comes from"), identifier: "hub.back", onBack: actions.onBack)
                switch state.phase {
                case .loading:
                    skeleton
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    if !state.summary.isEmpty {
                        Text(state.summary)
                            .font(ForecastFont.body)
                            .foregroundStyle(Theme.Palette.muted)
                            .fixedSize(horizontal: false, vertical: true)
                            .accessibilityIdentifier("hub.summary")
                    }
                    ForEach(Array(state.cards.enumerated()), id: \.element.id) { index, card in
                        cardButton(card, alt: !index.isMultiple(of: 2))
                    }
                }
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s).padding(.bottom, 112)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    /// The shape of the real list while nothing is saved yet (ADR 0060).
    private var skeleton: some View {
        VStack(alignment: .leading, spacing: 14) {
            LLSkeleton(.line(width: 0.9))
            LLSkeleton(.line(width: 0.6))
            ForEach(0..<4, id: \.self) { _ in SkeletonCard() }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(L10n.tr("Loading"))
        .accessibilityIdentifier("hub.skeleton")
    }

    private func cardButton(_ card: SourcesHubViewState.Card, alt: Bool) -> some View {
        Button { actions.onSelect(card.id) } label: {
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.s) {
                    Text(card.name).font(ForecastFont.section).frame(maxWidth: .infinity, alignment: .leading)
                    Chevron()
                }
                SourceStatusLine(card: card)
                Text(card.gives).font(ForecastFont.body).fixedSize(horizontal: false, vertical: true)
                if let usedIn = card.usedInText {
                    Text(usedIn).font(ForecastFont.caption).foregroundStyle(Theme.Palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .multilineTextAlignment(.leading)
            .padding(Theme.Spacing.l)
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .foregroundStyle(Theme.Palette.ink)
            .inkSurface(alt ? .cardAlt : .card)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(card.accessibilitySummary)
        .accessibilityHint(L10n.tr("Shows the latest values"))
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier("hub.card.\(card.id)")
    }
}

/// Status chip ("Live", "Saved copy") and "Updated 5 min ago".
struct SourceStatusLine: View {
    let card: SourcesHubViewState.Card

    var body: some View {
        FlowRow(spacing: 8) {
            HStack(spacing: 6) {
                Circle().fill(dot).overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: 1.5))
                    .frame(width: 10, height: 10)
                    .accessibilityHidden(true)
                Text(card.statusText).font(ForecastFont.captionBold)
            }
            .foregroundStyle(Theme.Palette.onArea)
            .padding(.horizontal, 10).padding(.vertical, 3)
            .background(Capsule().fill(fill))
            .overlay(Capsule().strokeBorder(Theme.Palette.ink, lineWidth: 2))
            if let updated = card.updatedText {
                Text(updated).font(ForecastFont.caption).foregroundStyle(Theme.Palette.muted)
                    .padding(.vertical, 4)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("hub.status.\(card.id)")
    }

    private var fill: Color {
        switch card.status {
        case .live: ForecastPalette.greenTint
        case .cached: Theme.Palette.surface
        case .mock, .unavailable: ForecastPalette.orangeTint
        }
    }

    private var dot: Color {
        switch card.status {
        case .live: Theme.Palette.money
        case .cached: Theme.Palette.other
        case .mock, .unavailable: Theme.Palette.home
        }
    }
}

/// One source: status, what it gives, the latest values with their dates, the screens that use it and
/// "Open the official page" (Safari).
struct SourceDetailView: View {
    let card: SourcesHubViewState.Card
    var onBack: () -> Void = {}
    @Environment(\.openURL) private var openURL

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                ForecastScreenHeader(title: card.name, identifier: "hub.detail.back", onBack: onBack)
                SourceStatusLine(card: card)
                Text(card.gives).font(ForecastFont.body).fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("hub.detail.gives")
                if !card.latest.isEmpty {
                    ForecastSectionTitle(title: L10n.tr("Latest values"))
                    VStack(spacing: 0) {
                        ForEach(card.latest) { value in
                            if value.id > 0 { RuleDivider() }
                            valueRow(value)
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.l)
                    .padding(.vertical, 6)
                    .frame(maxWidth: .infinity)
                    .foregroundStyle(Theme.Palette.ink)
                    .inkSurface(.card)
                }
                if let usedIn = card.usedInText {
                    Text(usedIn).font(ForecastFont.row).foregroundStyle(Theme.Palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if let url = card.url {
                    Button(L10n.tr("Open the official page")) { openURL(url) }
                        .buttonStyle(ForecastButtonStyle(filled: true, height: 52))
                        .padding(.top, 8)
                        .accessibilityHint(L10n.tr("Opens in Safari"))
                        .accessibilityIdentifier("hub.detail.open")
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s).padding(.bottom, 112)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    private func valueRow(_ value: SourcesHubViewState.Value) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                labelStack(value).frame(maxWidth: .infinity, alignment: .leading)
                Text(value.value).font(ForecastFont.rowBold).monospacedDigit().multilineTextAlignment(.trailing)
            }
            VStack(alignment: .leading, spacing: 2) {
                labelStack(value)
                Text(value.value).font(ForecastFont.rowBold).monospacedDigit()
            }
        }
        .padding(.vertical, 10)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("hub.detail.value.\(value.id)")
    }

    private func labelStack(_ value: SourcesHubViewState.Value) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value.label).font(ForecastFont.row).fixedSize(horizontal: false, vertical: true)
            if let asOf = value.asOfText {
                Text(asOf).font(ForecastFont.caption).foregroundStyle(Theme.Palette.muted)
            }
        }
    }
}

// MARK: - Previews (light, dark, AX3)

#Preview("Hub · light") {
    SourcesHubView(state: SourcesHubFixtures.ready).previewInNavigation()
}

#Preview("Hub · dark") {
    SourcesHubView(state: SourcesHubFixtures.ready).previewInNavigation().previewDark()
}

#Preview("Hub · AX3") {
    SourcesHubView(state: SourcesHubFixtures.ready).previewInNavigation().previewLargeType()
}

#Preview("Hub loading · light") {
    SourcesHubView(state: SourcesHubFixtures.loading).previewInNavigation()
}

#Preview("Detail · light") {
    SourceDetailView(card: SourcesHubFixtures.boe).previewInNavigation()
}

#Preview("Detail · dark") {
    SourceDetailView(card: SourcesHubFixtures.boe).previewInNavigation().previewDark()
}

#Preview("Detail · AX3") {
    SourceDetailView(card: SourcesHubFixtures.boe).previewInNavigation().previewLargeType()
}
