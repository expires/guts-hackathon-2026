import SwiftUI

/// Main game screen: who you are, stats, Index, net worth, AGE, and the year-by-year feed.
struct LifeView: View {
    let state: LifeViewState
    var actions: LifeActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var confirmNewLife = false

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.l) {
                if state.usesSampleData {
                    DemoDataBadge()
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                LifeHeaderView(header: state.header)
                MoneyCard(netWorth: state.netWorth, index: state.index)
                StatsCard(stats: state.stats)
                if let outcome = state.outcome {
                    OutcomeBanner(outcome: outcome, onDismiss: actions.onDismissOutcome)
                        .transition(Motion.transition(reduceMotion: reduceMotion))
                }
                if state.showsSummary {
                    PrimaryButton(title: "See your life summary", systemImage: "rosette", action: actions.onOpenSummary)
                        .accessibilityIdentifier("life.summary")
                } else if state.showsDecision {
                    PrimaryButton(title: "Your real-life decision", systemImage: "lightbulb", action: actions.onOpenDecision)
                        .accessibilityIdentifier("life.decision")
                }
                AgeButton(state: state, onAge: actions.onAge)
                QuickLinks(state: state, actions: actions)
                HistoryFeedView(history: state.history)
            }
            .padding(Theme.Spacing.l)
            .animation(Motion.standard(reduceMotion: reduceMotion), value: state)
        }
        .navigationTitle(state.header.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                Button("New life", systemImage: "arrow.uturn.backward") { confirmNewLife = true }
                    .accessibilityIdentifier("life.newLife")
            }
            ToolbarItem(placement: .topBarTrailing) {
                Button("Where the numbers come from", systemImage: "info.circle", action: actions.onOpenSources)
                    .accessibilityIdentifier("life.sources")
            }
        }
        .confirmationDialog("Start a new life?", isPresented: $confirmNewLife, titleVisibility: .visible) {
            Button("Start a new life", role: .destructive, action: actions.onNewLife)
            Button("Keep playing", role: .cancel) {}
        } message: {
            Text("You leave this life. You cannot come back to it.")
        }
    }
}

/// Emoji avatar, name, age, year, job and town.
struct LifeHeaderView: View {
    let header: LifeViewState.Header

    var body: some View {
        HStack(spacing: Theme.Spacing.l) {
            Text(header.emoji)
                .font(.system(size: 64))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                Text(header.name)
                    .font(.title.bold())
                HStack(spacing: Theme.Spacing.s) {
                    Text("Age \(header.age)")
                        .contentTransition(.numericText(value: Double(header.age)))
                        .accessibilityIdentifier("life.age")
                    Text("·").accessibilityHidden(true)
                    Text(String(header.year))
                        .contentTransition(.numericText(value: Double(header.year)))
                        .accessibilityIdentifier("life.year")
                }
                .font(.headline.monospacedDigit())
                Text("\(header.jobTitle), \(header.town)")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                if !header.isAlive {
                    Text("Died: \(header.causeOfDeath ?? "unknown cause")")
                        .font(.subheadline.bold())
                        .foregroundStyle(.red)
                }
            }
            Spacer(minLength: 0)
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("life.header")
    }
}

/// Net worth and Index.
struct MoneyCard: View {
    let netWorth: Double
    let index: Double

    var body: some View {
        GlassCard {
            HStack(alignment: .firstTextBaseline) {
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    Text("Net worth")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text(Money.format(netWorth))
                        .font(.largeTitle.bold().monospacedDigit())
                        .foregroundStyle(netWorth < 0 ? .red : .primary)
                        .contentTransition(.numericText(value: netWorth))
                        .minimumScaleFactor(0.6)
                        .lineLimit(1)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Net worth")
                .accessibilityValue(Money.spoken(netWorth))
                .accessibilityIdentifier("life.netWorth")

                Spacer()

                VStack(alignment: .trailing, spacing: Theme.Spacing.xs) {
                    Text("Index")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text(index.formatted(.number.precision(.fractionLength(0))))
                        .font(.title.bold().monospacedDigit())
                        .contentTransition(.numericText(value: index))
                    Text("100 = autopilot life")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Index")
                .accessibilityValue("\(Int(index.rounded())). 100 means the same as the autopilot life.")
                .accessibilityIdentifier("life.index")
            }
        }
    }
}

/// Happiness, Health, Smarts, Money.
struct StatsCard: View {
    let stats: [StatState]

    var body: some View {
        GlassCard {
            VStack(spacing: Theme.Spacing.m) {
                ForEach(stats) { StatBar(stat: $0) }
            }
        }
    }
}

/// The big AGE button. One tap = one year.
struct AgeButton: View {
    let state: LifeViewState
    let onAge: () -> Void

    var body: some View {
        VStack(spacing: Theme.Spacing.s) {
            Button(action: onAge) {
                HStack(spacing: Theme.Spacing.s) {
                    if state.isAging {
                        ProgressView()
                    } else {
                        Image(systemName: "plus.circle.fill")
                    }
                    Text("AGE")
                }
                .font(.title.bold())
                .frame(maxWidth: .infinity, minHeight: 64)
            }
            .buttonStyle(.glassProminent)
            .disabled(!state.canAge)
            .sensoryFeedback(.impact(weight: .medium), trigger: state.ageCount)
            .accessibilityLabel("Age one year")
            .accessibilityHint(state.ageHint)
            .accessibilityIdentifier("life.ageButton")

            Text(state.ageHint)
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }
}

/// Activities, Rewind and Concepts shortcuts.
struct QuickLinks: View {
    let state: LifeViewState
    let actions: LifeActions

    var body: some View {
        GlassEffectContainer(spacing: Theme.Spacing.s) {
            HStack(spacing: Theme.Spacing.s) {
                Button(action: actions.onOpenActivities) {
                    Label("Activities", systemImage: "figure.walk")
                        .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                }
                .buttonStyle(.glass)
                .accessibilityIdentifier("life.activities")

                Button(action: actions.onOpenRewind) {
                    Label("Rewind", systemImage: "backward.fill")
                        .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                }
                .buttonStyle(.glass)
                .disabled(!state.canRewind)
                .accessibilityHint(state.rewindText)
                .accessibilityIdentifier("life.rewind")

                Button(action: actions.onOpenConcepts) {
                    Label("\(state.conceptsUnlocked)", systemImage: "books.vertical")
                        .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                }
                .buttonStyle(.glass)
                .accessibilityLabel("Concepts, \(state.conceptsUnlocked) unlocked")
                .accessibilityIdentifier("life.concepts")
            }
        }
        .font(.subheadline.weight(.semibold))
    }
}

/// Result of the last choice, with money and stat changes.
struct OutcomeBanner: View {
    let outcome: OutcomeState
    let onDismiss: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            Image(systemName: outcome.isGood ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                .foregroundStyle(outcome.isGood ? .green : .orange)
                .font(.title2)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                Text(outcome.text).font(.body)
                if !outcome.changes.isEmpty {
                    Text(outcome.changes.joined(separator: "  ·  "))
                        .font(.footnote.monospacedDigit())
                        .foregroundStyle(.secondary)
                }
            }
            Spacer(minLength: 0)
            Button("Close", systemImage: "xmark", action: onDismiss)
                .labelStyle(.iconOnly)
                .frame(minWidth: Theme.minTarget, minHeight: Theme.minTarget)
                .accessibilityLabel("Close result")
        }
        .padding(Theme.Spacing.l)
        .glassEffect(.regular.tint((outcome.isGood ? Color.green : Color.orange).opacity(0.15)), in: .rect(cornerRadius: Theme.cornerRadius))
        .sensoryFeedback(outcome.isGood ? .success : .warning, trigger: outcome)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("life.outcome")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("New life · light") {
    LifeView(state: Fixtures.LifeScreen.newLife).previewInNavigation()
}

#Preview("New life · dark") {
    LifeView(state: Fixtures.LifeScreen.newLife).previewInNavigation().previewDark()
}

#Preview("New life · AX3") {
    LifeView(state: Fixtures.LifeScreen.newLife).previewInNavigation().previewLargeType()
}

#Preview("Mid-life · light") {
    LifeView(state: Fixtures.LifeScreen.midLife).previewInNavigation()
}

#Preview("Mid-life · dark") {
    LifeView(state: Fixtures.LifeScreen.midLife).previewInNavigation().previewDark()
}

#Preview("Mid-life · AX3") {
    LifeView(state: Fixtures.LifeScreen.midLife).previewInNavigation().previewLargeType()
}

#Preview("Event open · light") {
    LifeView(state: Fixtures.LifeScreen.eventOpen).previewInNavigation()
}

#Preview("Event open · dark") {
    LifeView(state: Fixtures.LifeScreen.eventOpen).previewInNavigation().previewDark()
}

#Preview("Event open · AX3") {
    LifeView(state: Fixtures.LifeScreen.eventOpen).previewInNavigation().previewLargeType()
}

#Preview("Bad outcome · light") {
    LifeView(state: Fixtures.LifeScreen.badOutcome).previewInNavigation()
}

#Preview("Bad outcome · dark") {
    LifeView(state: Fixtures.LifeScreen.badOutcome).previewInNavigation().previewDark()
}

#Preview("Bad outcome · AX3") {
    LifeView(state: Fixtures.LifeScreen.badOutcome).previewInNavigation().previewLargeType()
}

#Preview("Dead · light") {
    LifeView(state: Fixtures.LifeScreen.dead).previewInNavigation()
}

#Preview("Dead · dark") {
    LifeView(state: Fixtures.LifeScreen.dead).previewInNavigation().previewDark()
}

#Preview("Dead · AX3") {
    LifeView(state: Fixtures.LifeScreen.dead).previewInNavigation().previewLargeType()
}
