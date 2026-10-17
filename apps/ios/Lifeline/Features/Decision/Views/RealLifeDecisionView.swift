import SwiftUI

/// One clear recommended action for the player's real situation, with evidence.
struct RealLifeDecisionView: View {
    let state: RealLifeDecisionViewState
    var actions: RealLifeDecisionActions = .noop

    var body: some View {
        NavigationStack {
            ScrollView {
                switch state.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    content
                }
            }
            .navigationTitle("Your real decision")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close", action: actions.onClose)
                }
            }
        }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            Text(state.question).font(.headline).foregroundStyle(.secondary)
            Text(state.headline)
                .font(.largeTitle.bold())
                .accessibilityIdentifier("decision.headline")
            GlassCard {
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Text(state.evidenceSentence).font(.title3.weight(.semibold))
                    ProgressView(value: state.successRate)
                        .tint(.green)
                        .accessibilityLabel("Success rate")
                        .accessibilityValue("\(Int((state.successRate * 100).rounded())) percent")
                    Text("Based on \(state.twinsCount) similar lives in \(state.periods.joined(separator: ", ")).")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                SectionTitle(text: "Why")
                ForEach(state.reasons, id: \.self) { reason in
                    Label(reason, systemImage: "checkmark.circle")
                }
            }
            if !state.alternatives.isEmpty {
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    SectionTitle(text: "Other options")
                    ForEach(state.alternatives) { alternative in
                        HStack {
                            Text(alternative.label)
                            Spacer()
                            Text("\(Int((alternative.successRate * 10).rounded())) in 10 did better")
                                .font(.subheadline.monospacedDigit())
                                .foregroundStyle(.secondary)
                        }
                        .frame(minHeight: Theme.minTarget)
                        .accessibilityElement(children: .combine)
                    }
                }
            }
            SourcesFooter(sources: state.sources)
            Text(state.disclaimer)
                .font(.footnote)
                .foregroundStyle(.secondary)
                .accessibilityIdentifier("decision.disclaimer")
        }
        .padding(Theme.Spacing.l)
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
