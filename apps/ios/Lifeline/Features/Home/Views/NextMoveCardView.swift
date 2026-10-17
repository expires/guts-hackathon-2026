// Draft by W6. Owned by the UI owner from creation.
import SwiftUI

/// "What is my next money move?" The first element on the Money tab (ADR 0018).
struct NextMoveCardView: View {
    let state: NextMoveCardState
    var actions: NextMoveActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text(state.question)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(.secondary)
                switch state.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    if let move = state.displayedMove {
                        moveBody(move)
                    } else {
                        Text("No move right now. Your money looks fine.")
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: state)
        .accessibilityIdentifier("nextMove.card")
    }

    @ViewBuilder
    private func moveBody(_ move: NextMoveCardState.Move) -> some View {
        if state.focusedMoveID != nil {
            Button("Back to your top move", systemImage: "chevron.left") { actions.onFocus(nil) }
                .font(.footnote)
                .frame(minHeight: Theme.minTarget)
                .accessibilityIdentifier("nextMove.backToTop")
        }
        Label(move.headline, systemImage: MoveKindStyle.systemImage(move.kind))
            .font(.headline)
            .accessibilityIdentifier("nextMove.headline")
        Text(move.action)
            .font(.largeTitle.bold())
            .accessibilityIdentifier("nextMove.action")
        Text(move.impactText)
            .font(.title3.weight(.semibold).monospacedDigit())
            .foregroundStyle(move.impactPerYear >= 0 ? .green : .red)
            .contentTransition(.numericText(value: move.impactPerYear))
            .accessibilityIdentifier("nextMove.impact")
        Label(move.confidenceLabel, systemImage: "person.3")
            .font(.subheadline)
            .accessibilityIdentifier("nextMove.confidence")
        Text(move.worstCaseText)
            .font(.footnote)
            .foregroundStyle(.secondary)
        if let deadline = move.deadlineText {
            Label(deadline, systemImage: "calendar.badge.clock")
                .font(.subheadline.weight(.medium))
                .foregroundStyle(.orange)
                .accessibilityIdentifier("nextMove.deadline")
        }
        if !move.sources.isEmpty {
            FlowRow(spacing: Theme.Spacing.s) {
                ForEach(move.sources) { SourceChip(source: $0) }
            }
        }
        if state.isSampleData {
            DemoDataBadge()
        }
        buttons(move)
        if let message = state.planMessage {
            Button(message, systemImage: "checklist", action: actions.onOpenPlan)
                .font(.footnote)
                .frame(minHeight: Theme.minTarget)
                .accessibilityIdentifier("nextMove.planMessage")
        }
        if let backtest = state.backtestText, state.focusedMoveID == nil {
            Text(backtest)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        if state.focusedMoveID == nil, !state.runnersUp.isEmpty {
            Divider()
            Text("Other moves")
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.secondary)
            ForEach(state.runnersUp) { runnerUp in
                Button { actions.onFocus(runnerUp.id) } label: {
                    HStack {
                        VStack(alignment: .leading) {
                            Text(runnerUp.action).font(.subheadline.weight(.semibold))
                            Text(runnerUp.impactText).font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Image(systemName: "chevron.right").foregroundStyle(.tertiary)
                    }
                    .frame(minHeight: Theme.minTarget)
                    .contentShape(.rect)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("nextMove.runnerUp.\(runnerUp.id)")
            }
        }
    }

    private func buttons(_ move: NextMoveCardState.Move) -> some View {
        GlassEffectContainer(spacing: Theme.Spacing.s) {
            VStack(spacing: Theme.Spacing.s) {
                HStack(spacing: Theme.Spacing.s) {
                    if move.isTestable {
                        Button { actions.onTestIt(move.id) } label: {
                            Label("Test it", systemImage: "play.circle").frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                        }
                        .buttonStyle(.glass)
                        .accessibilityHint("Plays each option through a past period")
                        .accessibilityIdentifier("nextMove.testIt")
                    }
                    Button { actions.onWhy(move.id) } label: {
                        Label("Why?", systemImage: "questionmark.circle").frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                    }
                    .buttonStyle(.glass)
                    .accessibilityHint("Shows the evidence and the lesson")
                    .accessibilityIdentifier("nextMove.why")
                }
                Button { actions.onDoThis(move.id) } label: {
                    HStack {
                        if state.addingMoveID == move.id { ProgressView() }
                        Label(move.isInPlan ? "In your plan" : "Do this", systemImage: move.isInPlan ? "checkmark.circle.fill" : "plus.circle")
                    }
                    .font(.headline)
                    .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                }
                .buttonStyle(.glassProminent)
                .disabled(move.isInPlan || state.addingMoveID != nil)
                .accessibilityIdentifier("nextMove.doThis")
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.ready).padding() }
}

#Preview("Ready · dark") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.ready).padding() }.previewDark()
}

#Preview("Ready · AX3") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.ready).padding() }.previewLargeType()
}

#Preview("In plan · light") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.inPlan).padding() }
}

#Preview("Runner-up · light") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.focusedRunnerUp).padding() }
}

#Preview("Live, not testable · dark") {
    ScrollView { NextMoveCardView(state: Fixtures.NextMove.liveUntestable).padding() }.previewDark()
}

#Preview("Loading · light") {
    NextMoveCardView(state: Fixtures.NextMove.loading).padding()
}

#Preview("Error · light") {
    NextMoveCardView(state: Fixtures.NextMove.error).padding()
}
