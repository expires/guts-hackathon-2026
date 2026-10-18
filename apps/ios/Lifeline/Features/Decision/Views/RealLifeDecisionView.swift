import SwiftUI

/// One clear recommended action for the player's real situation, with evidence.
struct RealLifeDecisionView: View {
    let state: RealLifeDecisionViewState
    var actions: RealLifeDecisionActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: "Your real decision") {
                    HeaderSquareButton(kind: .close, identifier: "decision.close", action: actions.onClose)
                }
                switch state.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    content
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            Text(state.question).font(.llBodyBold).foregroundStyle(Theme.Palette.muted)
            Text(state.headline)
                .font(.llHero)
                .accessibilityIdentifier("decision.headline")
            InkCard {
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Text(state.evidenceSentence).font(.llTitle)
                    InkProgressBar(value: state.successRate, color: Theme.Palette.money)
                        .accessibilityElement()
                        .accessibilityLabel("Success rate")
                        .accessibilityValue(L10n.tr("\(Int((state.successRate * 100).rounded())) percent"))
                    Text(L10n.tr("Based on \(state.twinsCount) similar lives in \(state.periods.joined(separator: ", "))."))
                        .font(.llLabel)
                        .foregroundStyle(Theme.Palette.muted)
                }
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                SectionTitle(text: "Why")
                ForEach(state.reasons, id: \.self) { reason in
                    Label(reason, icon: .check)
                }
            }
            if !state.alternatives.isEmpty {
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    SectionTitle(text: "Other options")
                    ForEach(state.alternatives) { alternative in
                        HStack(alignment: .firstTextBaseline) {
                            Text(alternative.label).fixedSize(horizontal: false, vertical: true)
                            Spacer(minLength: Theme.Spacing.m)
                            Text(L10n.tr("\(Int((alternative.successRate * 10).rounded())) in 10 did better"))
                                .font(.llBody.monospacedDigit())
                                .foregroundStyle(Theme.Palette.muted)
                        }
                        .frame(minHeight: Theme.minTarget)
                        .accessibilityElement(children: .combine)
                    }
                }
            }
            SourcesFooter(sources: state.sources)
            Text(state.disclaimer)
                .font(.llLabel)
                .foregroundStyle(Theme.Palette.muted)
                .accessibilityIdentifier("decision.disclaimer")
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") {
    RealLifeDecisionView(state: Fixtures.Decision.ready)
}

#Preview("Ready · dark") {
    RealLifeDecisionView(state: Fixtures.Decision.ready).previewDark()
}

#Preview("Ready · AX3") {
    RealLifeDecisionView(state: Fixtures.Decision.ready).previewLargeType()
}

#Preview("Loading · light") {
    RealLifeDecisionView(state: Fixtures.Decision.loading)
}

#Preview("Loading · dark") {
    RealLifeDecisionView(state: Fixtures.Decision.loading).previewDark()
}

#Preview("Loading · AX3") {
    RealLifeDecisionView(state: Fixtures.Decision.loading).previewLargeType()
}

#Preview("Error · light") {
    RealLifeDecisionView(state: Fixtures.Decision.error)
}

#Preview("Error · dark") {
    RealLifeDecisionView(state: Fixtures.Decision.error).previewDark()
}

#Preview("Error · AX3") {
    RealLifeDecisionView(state: Fixtures.Decision.error).previewLargeType()
}
