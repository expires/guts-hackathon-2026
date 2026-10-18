import SwiftUI

/// Life main (handoff Life-Main): header with who you are and cash, the story feed by year,
/// the open event as a row, 4 stat bars, and the bottom bar with the Age button in the middle.
struct LifeView: View {
    let state: LifeViewState
    var actions: LifeActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var confirmNewLife = false

    var body: some View {
        VStack(spacing: 0) {
            header
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                    if let outcome = state.outcome {
                        OutcomeBanner(outcome: outcome, onDismiss: actions.onDismissOutcome)
                            .transition(Motion.transition(reduceMotion: reduceMotion))
                    }
                    if state.showsSummary {
                        PrimaryButton(title: L10n.tr("See your life summary"), icon: .ribbon, action: actions.onOpenSummary)
                            .accessibilityIdentifier("life.summary")
                    } else if state.showsDecision {
                        PrimaryButton(title: L10n.tr("Your real-life decision"), icon: .why, action: actions.onOpenDecision)
                            .accessibilityIdentifier("life.decision")
                    }
                    feed
                    VStack(spacing: Theme.Spacing.s) {
                        ForEach(state.stats) { StatRow(stat: $0) }
                    }
                    links
                }
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.top, Theme.Spacing.s).padding(.bottom, Theme.Spacing.m)
                .animation(Motion.standard(reduceMotion: reduceMotion), value: state)
            }
            bottomBar
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
        .confirmationDialog("Start a new life?", isPresented: $confirmNewLife, titleVisibility: .visible) {
            Button("Start a new life", role: .destructive, action: actions.onNewLife)
            Button("Keep playing", role: .cancel) {}
        } message: {
            Text("You leave this life. You cannot come back to it.")
        }
    }

    // MARK: Header

    private var header: some View {
        HStack(spacing: Theme.Spacing.m) {
            if let onExit = actions.onExit {
                HeaderSquareButton(kind: .back, identifier: "life.back", action: onExit)
            }
            LLIconImage(LLIcon.face(emoji: state.header.emoji), size: 40)
                .frame(width: 48, height: 48)
                .inkSurface(HandCut((18, 22, 17, 21), (21, 17, 22, 18)), fill: Theme.Palette.family)
            VStack(alignment: .leading, spacing: 2) {
                Text(state.header.name).font(.llBodyBold).lineLimit(1)
                HStack(spacing: 4) {
                    Text("Age \(state.header.age)")
                        .contentTransition(.numericText(value: Double(state.header.age)))
                        .accessibilityIdentifier("life.age")
                    Text(L10n.tr("· \(state.header.jobTitle) · \(state.header.town)")).lineLimit(1)
                }
                .font(.llLabel)
                .foregroundStyle(Theme.Palette.muted)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Button { actions.onOpenMenu(.money) } label: {
                VStack(alignment: .trailing, spacing: 0) {
                    Text(Money.format(state.cash))
                        .font(.llTitle)
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                        .contentTransition(.numericText(value: state.cash))
                    Text("In the bank").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                .frame(minHeight: Theme.minTarget)
            }
            .buttonStyle(.plain)
            .foregroundStyle(Theme.Palette.ink)
            .accessibilityLabel(L10n.tr("In the bank, \(Money.spoken(state.cash)). Open finances"))
            .accessibilityIdentifier("life.money")
        }
        .padding(.horizontal, Theme.Spacing.margin)
        .padding(.vertical, 14)
        .background(Theme.Palette.surface.ignoresSafeArea(edges: .top))
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.Palette.ink).frame(height: Theme.outline) }
    }

    // MARK: Feed

    @ViewBuilder
    private var feed: some View {
        let years = state.years
        if let current = years.first {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text(current.title)
                        .font(.llScreenTitle)
                        .accessibilityAddTraits(.isHeader)
                        .accessibilityIdentifier("life.year")
                    Spacer()
                    if state.usesSampleData { DemoDataBadge() }
                }
                ForEach(Array(current.lines.enumerated()), id: \.offset) { _, line in
                    Text(line).font(.llBody).fixedSize(horizontal: false, vertical: true)
                }
                if let event = state.pendingEvent {
                    Button(action: actions.onOpenEvent) {
                        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                            AreaChip(area: Area(rawValue: event.area) ?? .other, text: event.areaLabel)
                            HStack(spacing: Theme.Spacing.m) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(event.title).font(.llBodyBold)
                                    Text(event.subtitle).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                }
                                Spacer()
                                Chevron()
                            }
                        }
                        .padding(Theme.Spacing.l)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .inkSurface(.card, hero: true)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(Theme.Palette.ink)
                    .accessibilityIdentifier("life.pendingEvent")
                }
            }
        }
        ForEach(years.dropFirst()) { year in
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                Text(year.title).font(.llLabelBold)
                ForEach(Array(year.lines.enumerated()), id: \.offset) { _, line in
                    Text(line).font(.llBody).fixedSize(horizontal: false, vertical: true)
                }
            }
            .foregroundStyle(Theme.Palette.muted)
            .accessibilityElement(children: .combine)
        }
    }

    private var links: some View {
        FlowRow(spacing: Theme.Spacing.s) {
            Button("Rewind", action: actions.onOpenRewind)
                .buttonStyle(.text)
                .disabled(!state.canRewind)
                .accessibilityHint(state.rewindText)
                .accessibilityIdentifier("life.rewind")
            Button(L10n.tr("Concepts (\(state.conceptsUnlocked))"), action: actions.onOpenConcepts)
                .buttonStyle(.text)
                .accessibilityIdentifier("life.concepts")
            Button("Data sources", action: actions.onOpenSources)
                .buttonStyle(.text)
                .accessibilityIdentifier("life.sources")
            Button("New life") { confirmNewLife = true }
                .buttonStyle(.text)
                .accessibilityIdentifier("life.newLife")
        }
    }

    // MARK: Bottom bar

    /// Age up pill centred on its own row (below the bar's top line), the 4 menus under it.
    private var bottomBar: some View {
        VStack(spacing: Theme.Spacing.m) {
            AgeButton(state: state, onAge: actions.onAge)
                .padding(.bottom, Theme.heroShadow.height)
            HStack(alignment: .bottom, spacing: 0) {
                menuButton(.job)
                menuButton(.assets)
                menuButton(.people)
                menuButton(.activities)
            }
        }
        .padding(.horizontal, Theme.Spacing.m)
        .padding(.top, Theme.Spacing.m)
        .padding(.bottom, Theme.Spacing.s)
        .background(Theme.Palette.surface)
        .overlay(alignment: .top) { Rectangle().fill(Theme.Palette.ink).frame(height: Theme.outline) }
    }

    private func menuButton(_ menu: LifeMenuViewState.Menu) -> some View {
        let item = state.menu.items.first { $0.menu == menu }
        return Button { actions.onOpenMenu(menu) } label: {
            VStack(spacing: Theme.Spacing.xs) {
                LLIconImage(item?.icon ?? .activities, size: 40)
                Text(item?.title ?? "")
                    .font(.llLabelBold)
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
            }
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .foregroundStyle(Theme.Palette.ink)
        .disabled(!state.menu.isEnabled)
        .opacity(state.menu.isEnabled ? 1 : 0.45)
        .accessibilityLabel(item?.title ?? "")
        .accessibilityValue(item.map { $0.count == 1 ? "1 action" : "\($0.count) actions" } ?? "")
        .accessibilityIdentifier(menu == .activities ? "life.activities" : "lifeMenu.\(menu.rawValue)")
    }
}

/// Stat row from Life-Main: icon and label (112 pt), outlined bar, percent.
struct StatRow: View {
    let stat: StatState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(spacing: 10) {
            HStack(spacing: 6) {
                LLIconImage(Theme.icon(for: stat.kind), size: 24)
                Text(stat.kind.title).font(.llLabelBold).lineLimit(1).minimumScaleFactor(0.8)
            }
            .frame(width: 112, alignment: .leading)
            InkProgressBar(value: Double(stat.value) / 100, color: Theme.color(for: stat.kind), height: 14)
                .animation(Motion.standard(reduceMotion: reduceMotion), value: stat.value)
            Text("\(stat.value)%")
                .font(.llLabelBold)
                .frame(width: 40, alignment: .trailing)
                .contentTransition(.numericText(value: Double(stat.value)))
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(stat.kind.title)
        .accessibilityValue("\(stat.value) out of 100")
        .accessibilityIdentifier("stat.\(stat.kind.rawValue)")
    }
}

/// The Age up pill (`LLAgeUpButton`): "Age up → 30" from the engine's next age, pulsing cake while a year runs.
struct AgeButton: View {
    let state: LifeViewState
    let onAge: () -> Void

    var body: some View {
        LLAgeUpButton(nextAge: state.nextAge, isProcessing: state.isAging, hint: state.ageHint, action: onAge)
            .disabled(!state.canAge)
            .sensoryFeedback(.impact(weight: .medium), trigger: state.ageCount)
            .accessibilityIdentifier("life.ageButton")
    }
}

/// Result of the last choice or action. Area colour: money (good) or home (bad).
struct OutcomeBanner: View {
    let outcome: OutcomeState
    let onDismiss: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            LLIconImage(outcome.isGood ? .check : .crash, size: 32)
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                Text(outcome.text).font(.llBody).fixedSize(horizontal: false, vertical: true)
                if !outcome.changes.isEmpty {
                    Text(outcome.changes.joined(separator: "  ·  ")).font(.llLabelBold)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            HeaderSquareButton(kind: .close, identifier: "life.outcome.close", action: onDismiss)
        }
        .foregroundStyle(Theme.Palette.onArea)
        .padding(Theme.Spacing.l)
        .inkSurface(.card, fill: outcome.isGood ? Theme.Palette.money : Theme.Palette.home)
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

#Preview("Aging (processing) · light") {
    var state = Fixtures.LifeScreen.newLife
    state.isAging = true
    state.canAge = false
    return LifeView(state: state).previewInNavigation()
}
