// Draft by W6. Owned by the UI owner from creation.
import SwiftUI

/// "Guess my spend" (ADR 0017). Guess first; the prediction appears only after the guess.
struct GuessSpendCardView: View {
    let state: GuessSpendViewState
    var actions: GuessSpendActions = .noop
    @State private var entry = ""
    @FocusState private var entryFocused: Bool

    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                HStack {
                    Label("Guess my spend", systemImage: "sterlingsign.gauge.chart.lefthalf.righthalf")
                        .font(.headline)
                    Spacer()
                    if !state.isToday {
                        Button("Today", action: actions.onBackToToday)
                            .frame(minHeight: Theme.minTarget)
                            .accessibilityIdentifier("guess.today")
                    }
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
        }
        .accessibilityIdentifier("guess.card")
    }

    @ViewBuilder
    private var content: some View {
        Text(state.dateText).font(.subheadline.weight(.semibold))
        if let weather = state.weatherText {
            Label(weather, systemImage: "cloud.sun").font(.footnote).foregroundStyle(.secondary)
        }
        switch state.stage {
        case .guessing:
            Text("How much will you spend today? Guess first, then see what the model thinks.")
                .font(.subheadline)
            HStack(spacing: Theme.Spacing.s) {
                TextField("£0", text: $entry)
                    .keyboardType(.decimalPad)
                    .focused($entryFocused)
                    .textFieldStyle(.roundedBorder)
                    .frame(minHeight: Theme.minTarget)
                    .accessibilityLabel("Your guess in pounds")
                    .accessibilityIdentifier("guess.entry")
                Button {
                    entryFocused = false
                    actions.onSubmitGuess(entry)
                } label: {
                    HStack {
                        if state.isSubmitting { ProgressView() }
                        Text("Guess")
                    }
                    .frame(minHeight: Theme.minTarget)
                }
                .buttonStyle(.glassProminent)
                .disabled(state.isSubmitting || entry.isEmpty)
                .accessibilityIdentifier("guess.submit")
            }
        case .revealed:
            if let reveal = state.reveal { revealView(reveal) }
        }
        if let error = state.errorMessage {
            Text(error).font(.footnote).foregroundStyle(.red).accessibilityIdentifier("guess.error")
        }
        Text(state.streakText).font(.footnote)
        Text("\(state.pointsTotal) points so far").font(.footnote).foregroundStyle(.secondary)
        if !state.history.isEmpty {
            Divider()
            ForEach(state.history) { day in
                Button { actions.onSelectDay(day.id) } label: {
                    VStack(alignment: .leading) {
                        Text(day.dateText).font(.subheadline.weight(.semibold))
                        Text(day.summary).font(.caption).foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
                    .contentShape(.rect)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("guess.day.\(day.id)")
            }
        }
        if let accuracy = state.accuracyText {
            Button(accuracy, systemImage: "chart.xyaxis.line", action: actions.onOpenAccuracy)
                .font(.footnote)
                .frame(minHeight: Theme.minTarget)
                .accessibilityIdentifier("guess.accuracy")
        }
        if let link = state.moveLink {
            Button(link.text, systemImage: "arrow.up.circle") { actions.onShowMove(link.moveID) }
                .font(.footnote)
                .frame(minHeight: Theme.minTarget)
        }
        if state.isSampleData { DemoDataBadge() }
    }

    @ViewBuilder
    private func revealView(_ reveal: GuessSpendViewState.Reveal) -> some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading) {
                Text("Your guess").font(.caption).foregroundStyle(.secondary)
                Text(reveal.guessText).font(.title2.bold().monospacedDigit())
            }
            Spacer()
            VStack(alignment: .trailing) {
                Text("Model").font(.caption).foregroundStyle(.secondary)
                Text(reveal.predictedText)
                    .font(.title2.bold().monospacedDigit())
                    .contentTransition(.numericText(value: reveal.predicted))
                    .accessibilityIdentifier("guess.predicted")
            }
        }
        .accessibilityElement(children: .combine)
        Text(reveal.rangeText).font(.subheadline)
        Text(reveal.comparisonText).font(.subheadline)
        ForEach(reveal.reasons) { reason in
            HStack {
                Text(reason.label)
                Spacer()
                Text(reason.effectText).monospacedDigit().foregroundStyle(reason.effect >= 0 ? .orange : .green)
            }
            .font(.footnote)
            .accessibilityElement(children: .combine)
        }
        if let actual = reveal.actualText {
            Text(actual).font(.subheadline.weight(.semibold)).accessibilityIdentifier("guess.actual")
        }
        if let result = reveal.resultText {
            Label(result, systemImage: reveal.beatModel == true ? "trophy.fill" : "chart.bar")
                .font(.subheadline.weight(.semibold))
                .accessibilityIdentifier("guess.result")
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Before guess · light") {
    ScrollView { GuessSpendCardView(state: Fixtures.Guess.beforeGuess).padding() }
}

#Preview("Before guess · dark") {
    ScrollView { GuessSpendCardView(state: Fixtures.Guess.beforeGuess).padding() }.previewDark()
}

#Preview("Before guess · AX3") {
    ScrollView { GuessSpendCardView(state: Fixtures.Guess.beforeGuess).padding() }.previewLargeType()
}

#Preview("Revealed · light") {
    ScrollView { GuessSpendCardView(state: Fixtures.Guess.revealed).padding() }
}

#Preview("Past day · dark") {
    ScrollView { GuessSpendCardView(state: Fixtures.Guess.pastDay).padding() }.previewDark()
}

#Preview("Invalid entry · light") {
    ScrollView { GuessSpendCardView(state: Fixtures.Guess.invalidEntry).padding() }
}

#Preview("Loading · light") {
    GuessSpendCardView(state: Fixtures.Guess.loading).padding()
}
