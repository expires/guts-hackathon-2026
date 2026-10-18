import SwiftUI

/// "Your next money move": the hero card on the Money tab (ADR 0018, handoff A2-Money).
/// White card, 3 pt ink outline, hand-cut corners, offset shadow, Penny on the top edge.
struct NextMoveCardView: View {
    let state: NextMoveCardState
    var actions: NextMoveActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Text("Your next money move")
                .llEyebrow()
                .accessibilityAddTraits(.isHeader)
            switch state.phase {
            case let .loading(loading):
                LoadingStateView(state: loading)
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                if let move = state.displayedMove {
                    moveBody(move)
                } else {
                    Text("No move right now. Your money looks fine.").font(.llBody)
                }
            }
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .foregroundStyle(Theme.Palette.ink)
        .inkSurface(.hero, hero: true)
        .overlay(alignment: .topTrailing) {
            if let move = state.displayedMove, state.phase == .ready {
                PennyView(mood: PennyView.mood(confidence: move.confidence), size: 66)
                    .rotationEffect(.degrees(8))
                    .offset(x: -18, y: -34)
                    .accessibilityHidden(true)
            }
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: state)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("nextMove.card")
    }

    @ViewBuilder
    private func moveBody(_ move: NextMoveCardState.Move) -> some View {
        if state.focusedMoveID != nil {
            Button { actions.onFocus(nil) } label: {
                HStack(spacing: Theme.Spacing.s) {
                    Chevron(direction: .left)
                    Text("Back to your top move")
                }
            }
            .buttonStyle(.text)
            .accessibilityIdentifier("nextMove.backToTop")
        }
        VStack(alignment: .leading, spacing: 6) {
            Text(move.action)
                .font(.llTitle)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
                .accessibilityIdentifier("nextMove.action")
            Text(move.headline)
                .font(.llBody)
                .accessibilityIdentifier("nextMove.headline")
        }
        impactRow(move)
        if let tradeOff = move.tradeOffText {
            Text(tradeOff)
                .font(.llLabel)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("nextMove.tradeOff")
        }
        buttons(move)
        if let sources = state.sourceCountText {
            Button { actions.onSources(move.id) } label: {
                HStack(spacing: Theme.Spacing.xs) {
                    LLIconImage(.statusLive, size: 24)
                    Text(sources)
                }
            }
            .buttonStyle(.text)
            .font(.llLabelBold)
            .accessibilityHint("Shows the sources in Why?")
            .accessibilityIdentifier("nextMove.sources")
        }
        if let message = state.planMessage {
            Button(message, action: actions.onOpenPlan)
                .buttonStyle(.text)
                .font(.llLabelBold)
                .accessibilityIdentifier("nextMove.planMessage")
        }
    }

    /// £ a year (40) on the left, confidence word, meter and reason on the right, between two ink rules.
    private func impactRow(_ move: NextMoveCardState.Move) -> some View {
        HStack(alignment: .center, spacing: Theme.Spacing.l) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                if move.isGainMissing {
                    // No costs entered: ask for them instead of a number.
                    Text(move.impactCaption)
                        .font(.llBodyBold)
                        .fixedSize(horizontal: false, vertical: true)
                } else {
                    Text(move.impactAmountText)
                        .font(move.isMonthsOfCover ? .llTitle : .llHero)
                        .contentTransition(.numericText(value: move.impactPerYear))
                        .minimumScaleFactor(0.6)
                        .lineLimit(1)
                    Text(move.impactCaption).font(.llLabel)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("nextMove.impact")
            if !move.confidenceText.isEmpty {
                Rectangle().fill(Theme.Palette.ink).frame(width: Theme.outline).clipShape(.capsule)
                VStack(alignment: .leading, spacing: 6) {
                    if move.confidenceFilled > 0 { ConfidenceMeter(filled: move.confidenceFilled) }
                    Text(move.confidenceText).font(.llLabelBold).fixedSize(horizontal: false, vertical: true)
                    Text(move.confidenceLabel).font(.llLabel).fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("nextMove.confidence")
            }
        }
        .padding(.vertical, Theme.Spacing.m)
        .overlay(alignment: .top) { Rectangle().fill(Theme.Palette.ink).frame(height: Theme.outline) }
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.Palette.ink).frame(height: Theme.outline) }
    }

    /// One row when every label fits at its full width, else stacked (large Dynamic Type never cuts "Test it").
    private func buttons(_ move: NextMoveCardState.Move) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: Theme.Spacing.s) { buttonRow(move) }
            VStack(spacing: Theme.Spacing.s) { buttonRow(move) }
        }
    }

    /// "Test it" shows for every testable move: top move, focused runner-up, in plan or not (ADR 0070).
    static func showsTestIt(_ move: NextMoveCardState.Move) -> Bool {
        move.isTestable
    }

    @ViewBuilder
    private func buttonRow(_ move: NextMoveCardState.Move) -> some View {
        if Self.showsTestIt(move) {
            Button { actions.onTestIt(move.id) } label: {
                HStack(spacing: Theme.Spacing.s) {
                    LLIconImage(.test, size: 24)
                    Text("Test it").lineLimit(1).fixedSize()
                }
            }
            .buttonStyle(.main)
            .accessibilityHint("Plays each option through a past period")
            .accessibilityIdentifier("nextMove.testIt")
        }
        Button { actions.onWhy(move.id) } label: { Text("Why?").lineLimit(1).fixedSize() }
            .buttonStyle(.second)
            .accessibilityHint("Shows the evidence and the lesson")
            .accessibilityIdentifier("nextMove.why")
        Button { actions.onDoThis(move.id) } label: {
            HStack(spacing: Theme.Spacing.xs) {
                if state.addingMoveID == move.id { ProgressView() }
                if move.isInPlan { LLIconImage(.check, size: 24) }
                Text(move.isInPlan ? "In plan" : "Do this").lineLimit(1).fixedSize()
            }
        }
        .buttonStyle(SecondButtonStyle(shape: .buttonThird))
        .disabled(move.isInPlan || state.addingMoveID != nil)
        .accessibilityLabel(move.isInPlan ? "In your plan" : "Do this")
        .accessibilityIdentifier("nextMove.doThis")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.ready).padding(20).padding(.top, 30) }.paperBackground()
}

#Preview("Ready · dark") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.ready).padding(20).padding(.top, 30) }.paperBackground().previewDark()
}

#Preview("Ready · AX3") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.ready).padding(20).padding(.top, 30) }.paperBackground().previewLargeType()
}

#Preview("In plan · light") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.inPlan).padding(20).padding(.top, 30) }.paperBackground()
}

#Preview("Runner-up · light") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.focusedRunnerUp).padding(20).padding(.top, 30) }.paperBackground()
}

#Preview("Live, not testable · dark") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.liveUntestable).padding(20).padding(.top, 30) }.paperBackground().previewDark()
}

#Preview("Loading · light") {
    NextMoveCardView(state: Fixtures.NextMove.loading).padding(20).paperBackground()
}

#Preview("Error · light") {
    NextMoveCardView(state: Fixtures.NextMove.error).padding(20).paperBackground()
}
