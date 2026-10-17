import SwiftUI

/// Your money habits: one score ring and seven factors with bars.
struct HabitsView: View {
    let state: HabitsViewState
    var actions: HabitsActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: Theme.Spacing.l) {
                    switch state.phase {
                    case let .loading(loading):
                        LoadingStateView(state: loading)
                    case let .failed(error):
                        ErrorStateView(state: error, onRetry: actions.onRetry)
                    case .ready:
                        overallCard
                        ForEach(state.factors) { FactorRow(factor: $0) }
                    }
                }
                .padding(Theme.Spacing.l)
            }
            .animation(Motion.standard(reduceMotion: reduceMotion), value: state)
            .navigationTitle("Your money habits")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done", action: actions.onClose)
                        .frame(minWidth: Theme.minTarget, minHeight: Theme.minTarget)
                        .accessibilityIdentifier("habits.done")
                }
            }
        }
    }

    private var overallCard: some View {
        GlassCard {
            VStack(spacing: Theme.Spacing.m) {
                ScoreRing(score: state.overall)
                    .frame(width: 140, height: 140)
                if let band = state.overallBandText {
                    Text(band).font(.headline)
                }
                Text(state.windowText).font(.footnote).foregroundStyle(.secondary)
                if state.isSampleData { DemoDataBadge() }
            }
            .frame(maxWidth: .infinity)
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("habits.overall")
    }
}

private func scoreColor(_ score: Int) -> Color {
    switch score {
    case 70...: .green
    case 40..<70: .orange
    default: .red
    }
}

private struct ScoreRing: View {
    let score: Int?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            Circle().stroke(.quaternary, lineWidth: 14)
            Circle()
                .trim(from: 0, to: CGFloat(score ?? 0) / 100)
                .stroke(scoreColor(score ?? 0).gradient, style: StrokeStyle(lineWidth: 14, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .animation(Motion.standard(reduceMotion: reduceMotion), value: score)
            VStack(spacing: 0) {
                Text(score.map(String.init) ?? "-")
                    .font(.system(size: 44, weight: .bold, design: .rounded).monospacedDigit())
                    .contentTransition(.numericText(value: Double(score ?? 0)))
                Text("out of 100").font(.caption).foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Overall money habits score")
        .accessibilityValue(score.map { "\($0) out of 100" } ?? "Not available")
    }
}

private struct FactorRow: View {
    let factor: HabitsViewState.Factor
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                HStack(alignment: .firstTextBaseline) {
                    Text(factor.label).font(.headline)
                    Spacer()
                    if let band = factor.bandText {
                        Text(band).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    }
                }
                Text(factor.explainer).font(.subheadline).foregroundStyle(.secondary)
                if let score = factor.score {
                    GeometryReader { proxy in
                        ZStack(alignment: .leading) {
                            Capsule().fill(.quaternary)
                            Capsule()
                                .fill(scoreColor(score).gradient)
                                .frame(width: proxy.size.width * CGFloat(min(100, max(0, score))) / 100)
                        }
                    }
                    .frame(height: 8)
                    .animation(Motion.standard(reduceMotion: reduceMotion), value: score)
                    .accessibilityHidden(true)
                    Text(factor.scoreText).font(.footnote.monospacedDigit())
                } else if let reason = factor.reason {
                    Label(reason, systemImage: "info.circle")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(factor.label). \(factor.explainer)")
        .accessibilityValue(factor.score.map { "\($0) out of 100" } ?? (factor.reason ?? "Not available"))
        .accessibilityIdentifier("habits.factor.\(factor.id)")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") { HabitsView(state: Fixtures.Habits.ready) }
#Preview("Ready · dark") { HabitsView(state: Fixtures.Habits.ready).previewDark() }
#Preview("Ready · AX3") { HabitsView(state: Fixtures.Habits.ready).previewLargeType() }

#Preview("Live · light") { HabitsView(state: Fixtures.Habits.live) }
#Preview("Loading · light") { HabitsView(state: Fixtures.Habits.loading) }
#Preview("Error · light") { HabitsView(state: Fixtures.Habits.error) }
