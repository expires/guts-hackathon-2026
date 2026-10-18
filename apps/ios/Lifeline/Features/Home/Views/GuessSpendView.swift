import SwiftUI

/// "Guess my spend" game (handoff Money-Guess, ADR 0017).
/// Guess first with the stepper; Penny's range, the 3 reasons and the result appear only after "Lock in".
struct GuessSpendView: View {
    let state: GuessSpendViewState
    var actions: GuessSpendActions = .noop
    var onClose: () -> Void = {}
    @State private var guess: Double?

    private var currentGuess: Double { guess ?? state.initialGuess }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: "Guess my spend", leading: HeaderSquareButton(kind: .back, identifier: "guess.back", action: onClose)) {
                    OutlineTag(text: state.dayChip)
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
            .padding(Theme.Spacing.margin)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    @ViewBuilder
    private var content: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(state.stage == .guessing ? "How much will you spend today?" : "Your guess is in")
                .font(.llBodyBold)
            Text([state.dateText, state.weatherText, state.isSampleData ? "Mock data" : nil].compactMap { $0 }.joined(separator: " · "))
                .font(.llLabel)
                .foregroundStyle(Theme.Palette.muted)
        }
        switch state.stage {
        case .guessing:
            stepper
            Text("Penny shows her guess after you lock yours in.")
                .font(.llLabel)
                .foregroundStyle(Theme.Palette.muted)
            if let error = state.errorMessage {
                Text(error).font(.llLabelBold).accessibilityIdentifier("guess.error")
            }
            Button {
                actions.onSubmitGuess(String(format: "%.2f", currentGuess))
            } label: {
                HStack {
                    if state.isSubmitting { ProgressView().tint(Theme.Palette.surface) }
                    Text(L10n.tr("Lock in \(Money.format(currentGuess))"))
                }
            }
            .buttonStyle(.main)
            .disabled(state.isSubmitting)
            .accessibilityIdentifier("guess.submit")
        case .revealed:
            if let reveal = state.reveal {
                PennyCard(reveal: reveal)
                reasons(reveal)
                if let actual = reveal.actualText {
                    Text(actual).font(.llBodyBold).accessibilityIdentifier("guess.actual")
                }
                if let result = reveal.resultText {
                    Label(result, icon: reveal.beatModel == true ? .trophy : .streak, size: 32)
                        .font(.llBodyBold)
                        .accessibilityIdentifier("guess.result")
                }
            }
        }
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            // Both lines come from the guess history; without it, neither shows.
            if !state.streakText.isEmpty {
                Label(state.streakText, icon: .streak).font(.llLabel)
                Text(L10n.tr("\(state.pointsTotal) points so far")).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        }
        if !state.isToday {
            Button("Back to today", action: actions.onBackToToday)
                .buttonStyle(.text)
                .accessibilityIdentifier("guess.today")
        }
        if !state.history.isEmpty {
            VStack(alignment: .leading, spacing: 0) {
                Text("Past days").font(.llBodyBold).padding(.bottom, Theme.Spacing.xs)
                ForEach(Array(state.history.enumerated()), id: \.element.id) { offset, day in
                    Button { actions.onSelectDay(day.id) } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(day.dateText).font(.llBodyBold)
                                Text(day.summary).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                            }
                            Spacer()
                            Chevron()
                        }
                        .frame(minHeight: Theme.minTarget)
                        .contentShape(.rect)
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("guess.day.\(day.id)")
                    if offset < state.history.count - 1 { RuleDivider() }
                }
            }
        }
        if let accuracy = state.accuracyText {
            Button(accuracy, action: actions.onOpenAccuracy)
                .buttonStyle(.text)
                .font(.llLabelBold)
                .accessibilityIdentifier("guess.accuracy")
        }
        if let link = state.moveLink {
            NextMoveLinkRow(text: link.text) { actions.onShowMove(link.moveID) }
        }
    }

    private var stepper: some View {
        HStack(spacing: Theme.Spacing.m) {
            stepButton("−", label: L10n.tr("Guess £1 less"), shape: HandCut((16, 20, 15, 19))) { guess = max(0, currentGuess - 1) }
                .accessibilityIdentifier("guess.minus")
            VStack(spacing: 2) {
                Text("Your guess").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                Text(Money.format(currentGuess))
                    .font(.llHero)
                    .contentTransition(.numericText(value: currentGuess))
                    .accessibilityIdentifier("guess.value")
            }
            .frame(maxWidth: .infinity)
            .accessibilityElement(children: .combine)
            .accessibilityAdjustableAction { direction in
                switch direction {
                case .increment: guess = currentGuess + 1
                case .decrement: guess = max(0, currentGuess - 1)
                @unknown default: break
                }
            }
            stepButton("+", label: L10n.tr("Guess £1 more"), shape: HandCut((20, 16, 19, 15))) { guess = currentGuess + 1 }
                .accessibilityIdentifier("guess.plus")
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, 14)
        .inkSurface(HandCut((18, 24, 16, 22), (22, 16, 24, 18)))
    }

    private func stepButton(_ text: String, label: String, shape: HandCut, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(text).font(.llTitle).frame(width: 52, height: 52).inkSurface(shape)
        }
        .buttonStyle(.plain)
        .foregroundStyle(Theme.Palette.ink)
        .accessibilityLabel(label)
    }

    private func reasons(_ reveal: GuessSpendViewState.Reveal) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Top 3 reasons").font(.llBodyBold).padding(.bottom, Theme.Spacing.xs)
            ForEach(Array(reveal.reasons.enumerated()), id: \.element.id) { offset, reason in
                HStack(spacing: Theme.Spacing.m) {
                    Text(reason.label).font(.llBody).frame(maxWidth: .infinity, alignment: .leading)
                    Chip(text: reason.effectText, fill: reason.effect >= 0 ? Theme.Palette.health : Theme.Palette.money)
                }
                .frame(minHeight: Theme.minTarget)
                .accessibilityElement(children: .combine)
                if offset < reveal.reasons.count - 1 { RuleDivider() }
            }
            Text(reveal.baselineText).font(.llLabel).foregroundStyle(Theme.Palette.muted).padding(.top, 6)
        }
    }
}

/// "Penny thinks": range (40), the range bar with Penny's and your marks, the comparison.
private struct PennyCard: View {
    let reveal: GuessSpendViewState.Reveal

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Text("Penny thinks").llEyebrow()
            Text(reveal.rangeShortText).font(.llHero).lineLimit(1).minimumScaleFactor(0.6)
                .accessibilityIdentifier("guess.predicted")
            GeometryReader { proxy in
                let width = proxy.size.width
                ZStack(alignment: .leading) {
                    Rectangle().fill(Theme.Palette.surface)
                    Rectangle()
                        .fill(Theme.Palette.money)
                        .frame(width: max(0, width * (reveal.highFraction - reveal.lowFraction)))
                        .overlay { HStack { Rectangle().fill(Theme.Palette.ink).frame(width: 3); Spacer(); Rectangle().fill(Theme.Palette.ink).frame(width: 3) } }
                        .offset(x: width * reveal.lowFraction)
                    Rectangle().fill(Theme.Palette.ink).frame(width: 3).offset(x: width * reveal.predictedFraction - 1.5)
                }
                .clipShape(HandCut.bar)
                .overlay(HandCut.bar.strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline))
            }
            .frame(height: 22)
            GeometryReader { proxy in
                ZStack(alignment: .topLeading) {
                    Text("£0").font(.llLabel)
                    Text(reveal.scaleMaxText).font(.llLabel).frame(maxWidth: .infinity, alignment: .trailing)
                    VStack(spacing: 0) {
                        Text("▲").font(.llLabel).hidden()
                        Text("You \(reveal.guessText)").font(.llLabelBold)
                    }
                    .fixedSize()
                    .position(x: min(max(40, proxy.size.width * reveal.guessFraction), proxy.size.width - 40), y: 16)
                }
            }
            .frame(height: 34)
            Text(L10n.tr("Penny \(reveal.predictedText). \(reveal.comparisonText)")).font(.llBody)
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.hero, hero: true)
        .overlay(alignment: .topTrailing) {
            PennyView(mood: .neutral, size: 56).rotationEffect(.degrees(-6)).offset(x: -16, y: -26)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel(L10n.tr("Penny thinks \(reveal.rangeText). Penny \(reveal.predictedText). You \(reveal.guessText). \(reveal.comparisonText)"))
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Before guess · light") { GuessSpendView(state: Fixtures.Guess.beforeGuess) }
#Preview("Before guess · dark") { GuessSpendView(state: Fixtures.Guess.beforeGuess).previewDark() }
#Preview("Before guess · AX3") { GuessSpendView(state: Fixtures.Guess.beforeGuess).previewLargeType() }
#Preview("Revealed · light") { GuessSpendView(state: Fixtures.Guess.revealed) }
#Preview("Revealed · dark") { GuessSpendView(state: Fixtures.Guess.revealed).previewDark() }
#Preview("Past day · light") { GuessSpendView(state: Fixtures.Guess.pastDay) }
#Preview("Invalid entry · light") { GuessSpendView(state: Fixtures.Guess.invalidEntry) }
#Preview("Loading · light") { GuessSpendView(state: Fixtures.Guess.loading) }
