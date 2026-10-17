import SwiftUI

/// Your money habits: one score ring and seven factors with bars.
struct HabitsView: View {
    let state: HabitsViewState
    var actions: HabitsActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        SheetContainer(title: "Your money habits", closeIdentifier: "habits.done", onClose: actions.onClose) {
            switch state.phase {
            case let .loading(loading):
                LoadingStateView(state: loading)
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                overallCard
                if !state.factors.isEmpty {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        ChartHeader(title: "What makes up the score", help: ChartHelpCatalogue.habitFactors)
                        ChartCaption(help: ChartHelpCatalogue.habitFactors)
                    }
                }
                ForEach(state.factors) { FactorRow(factor: $0) }
            }
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: state)
        .background(Theme.Palette.paper)
    }

    private var overallCard: some View {
        InkCard(shape: .hero, hero: true, padding: Theme.Spacing.xl) {
            VStack(spacing: Theme.Spacing.m) {
                ScoreRing(score: state.overall)
                    .frame(width: 148, height: 148)
                ChartCaption(help: ChartHelpCatalogue.habitsScore)
                if let band = state.overallBandText {
                    Text(band).font(.llTitle)
                }
                Text(state.windowText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    .multilineTextAlignment(.center)
                if state.isSampleData { DemoDataBadge() }
            }
            .frame(maxWidth: .infinity)
        }
        .padding(.trailing, Theme.heroShadow.width)
        .padding(.bottom, Theme.heroShadow.height)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("habits.overall")
        .overlay(alignment: .topTrailing) {
            ChartInfoButton(help: ChartHelpCatalogue.habitsScore).padding(.trailing, Theme.heroShadow.width)
        }
    }
}

/// Green when going well, orange for fine, pink for worth a look. Always paired with words.
private func scoreColor(_ score: Int) -> Color {
    switch score {
    case 70...: Theme.Palette.money
    case 40..<70: Theme.Palette.home
    default: Theme.Palette.health
    }
}

private struct ScoreRing: View {
    let score: Int?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            Circle().stroke(Theme.Palette.rule, lineWidth: 16)
            Circle()
                .trim(from: 0, to: CGFloat(score ?? 0) / 100)
                .stroke(scoreColor(score ?? 0), style: StrokeStyle(lineWidth: 16, lineCap: .butt))
                .rotationEffect(.degrees(-90))
                .animation(Motion.standard(reduceMotion: reduceMotion), value: score)
            Circle().strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline)
            Circle().strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline).padding(16)
            VStack(spacing: 0) {
                Text(score.map(String.init) ?? "-")
                    .font(.llHero)
                    .contentTransition(.numericText(value: Double(score ?? 0)))
                Text("out of 100").font(.llLabel).foregroundStyle(Theme.Palette.muted)
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
        InkCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.s) {
                    Text(factor.label).font(.llBodyBold)
                    Spacer(minLength: Theme.Spacing.s)
                    if let band = factor.bandText, let score = factor.score {
                        Chip(text: band, fill: scoreColor(score))
                    }
                }
                Text(factor.explainer).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
                if let score = factor.score {
                    InkProgressBar(value: Double(min(100, max(0, score))) / 100, color: scoreColor(score), height: 14)
                        .animation(Motion.standard(reduceMotion: reduceMotion), value: score)
                        .accessibilityHidden(true)
                    Text(factor.scoreText).font(.llLabelBold.monospacedDigit())
                } else if let reason = factor.reason {
                    Label(reason, icon: .why)
                        .font(.llLabel)
                        .foregroundStyle(Theme.Palette.muted)
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
