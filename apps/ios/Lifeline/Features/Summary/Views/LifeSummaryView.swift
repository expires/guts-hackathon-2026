// Rebuilt for ADR 0026 (Life-Summary.dc.html) by W7.
import Charts
import SwiftUI

/// End of a life: INDEX score against the autopilot twin, ribbons, big moments.
struct LifeSummaryView: View {
    let state: LifeSummaryViewState
    var actions: LifeSummaryActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                switch state.phase {
                case let .loading(loading):
                    closeRow
                    LoadingStateView(state: loading)
                case let .failed(error):
                    closeRow
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

    private var closeRow: some View {
        HStack {
            Spacer()
            HeaderSquareButton(kind: .close, identifier: "summary.close", action: actions.onClose)
        }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            header
            indexCard
            if !state.ribbons.isEmpty { ribbons }
            if !state.keyMoments.isEmpty { moments }
            HStack(spacing: Theme.Spacing.s) {
                ShareLink(item: state.shareText) { Text("Share my life") }
                    .buttonStyle(.main)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .accessibilityIdentifier("summary.share")
                Button("Play again", action: actions.onNewLife)
                    .buttonStyle(.second)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .accessibilityIdentifier("summary.newLife")
            }
            // Every screen links back to the Next Move (ADR 0043).
            Button("Your next move", action: actions.onNextMove)
                .buttonStyle(.text)
                .accessibilityHint("Opens the Money tab with your Next Move")
                .accessibilityIdentifier("summary.nextMove")
        }
    }

    private var header: some View {
        HStack(spacing: Theme.Spacing.m) {
            LLIconImage(LLIcon.face(emoji: state.emoji), size: 40)
                .frame(width: 48, height: 48)
                .inkSurface(HandCut((18, 22, 17, 21), (21, 17, 22, 18)), fill: Theme.Palette.family)
            VStack(alignment: .leading, spacing: 0) {
                Text(state.title).font(.llTitle).accessibilityAddTraits(.isHeader)
                Text(state.lifespanText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                if let cause = state.causeOfDeath {
                    Text(cause).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            VStack(alignment: .trailing, spacing: Theme.Spacing.xs) {
                HeaderSquareButton(kind: .close, identifier: "summary.close", action: actions.onClose)
                if state.isSampleData { DemoDataBadge() } else { OutlineTag(text: "Game result") }
            }
        }
    }

    private var indexCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 14) {
                VStack(alignment: .leading, spacing: 0) {
                    Text("INDEX").font(.llLabelBold).tracking(1.04)
                    Text(state.indexText).font(.llHero)
                        .contentTransition(.numericText(value: state.finalIndex))
                }
                Text(state.indexSentence).font(.llBody)
            }
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("summary.totals")
            if state.timeline.count > 1 { chart }
            HStack {
                Text("Age \(state.timeline.first?.age ?? 0)")
                Spacer()
                Text("Net worth by age")
                Spacer()
                Text("\(state.timeline.last?.age ?? state.age)")
            }
            .font(.llLabel)
            .foregroundStyle(Theme.Palette.muted)
            Text(L10n.tr("You \(Money.format(state.netWorth)) · Autopilot \(Money.format(state.autopilotNetWorth))"))
                .font(.llLabelBold)
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.hero, hero: true)
    }

    private var chart: some View {
        Chart {
            ForEach(state.timeline) { point in
                LineMark(x: .value("Age", point.age), y: .value("Net worth", point.autopilotNetWorth), series: .value("Life", "Autopilot"))
                    .foregroundStyle(Theme.Palette.muted)
                    .lineStyle(StrokeStyle(lineWidth: 3, lineCap: .round, dash: [6, 6]))
                    .interpolationMethod(.monotone)
            }
            ForEach(state.timeline) { point in
                LineMark(x: .value("Age", point.age), y: .value("Net worth", point.netWorth), series: .value("Life", "You"))
                    .foregroundStyle(Theme.Palette.ink)
                    .lineStyle(StrokeStyle(lineWidth: 4, lineCap: .round))
                    .interpolationMethod(.monotone)
            }
            if let last = state.timeline.last {
                PointMark(x: .value("Age", last.age), y: .value("Net worth", last.netWorth))
                    .opacity(0)
                    .annotation(position: .top, alignment: .trailing) { Text("You").font(.llLabelBold) }
                PointMark(x: .value("Age", last.age), y: .value("Net worth", last.autopilotNetWorth))
                    .opacity(0)
                    .annotation(position: .bottom, alignment: .trailing) {
                        Text("Autopilot").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
            }
        }
        .chartXAxis(.hidden)
        .chartYAxis(.hidden)
        .chartXScale(domain: .automatic(includesZero: false))
        .frame(height: 110)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Net worth by age, you against your autopilot twin")
        .accessibilityValue(L10n.tr("You \(Money.spoken(state.netWorth)). Autopilot \(Money.spoken(state.autopilotNetWorth))."))
    }

    private var ribbons: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            BlockTitle(text: L10n.tr("Ribbons · \(state.ribbons.count) earned"))
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: Theme.Spacing.s, alignment: .top), count: 4), spacing: Theme.Spacing.m) {
                ForEach(Array(state.ribbons.enumerated()), id: \.element.id) { index, ribbon in
                    VStack(spacing: Theme.Spacing.xs) {
                        RibbonMedal(color: Area.cycling(index).color)
                        Text(ribbon.title)
                            .font(.llLabel)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .frame(maxWidth: .infinity)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("\(ribbon.title). \(ribbon.reason)")
                    .accessibilityIdentifier("summary.ribbon.\(ribbon.id)")
                }
            }
        }
    }

    private var moments: some View {
        VStack(alignment: .leading, spacing: 0) {
            BlockTitle(text: "Big moments").padding(.bottom, Theme.Spacing.xs)
            ForEach(Array(state.keyMoments.enumerated()), id: \.element.id) { offset, moment in
                if offset > 0 { RuleDivider() }
                HStack(spacing: 10) {
                    Text("\(moment.age)").font(.llLabelBold).frame(width: 32, alignment: .leading)
                    Text(moment.text).font(.llBody).frame(maxWidth: .infinity, alignment: .leading)
                    if let delta = moment.indexDelta {
                        Text(delta).font(.llLabelBold)
                            .accessibilityLabel("INDEX \(delta)")
                    }
                }
                .frame(minHeight: 40)
                .accessibilityElement(children: .combine)
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Death · light") { LifeSummaryView(state: Fixtures.Summary.death) }
#Preview("Death · dark") { LifeSummaryView(state: Fixtures.Summary.death).previewDark() }
#Preview("Death · AX3") { LifeSummaryView(state: Fixtures.Summary.death).previewLargeType() }
#Preview("Four ribbons · light") { LifeSummaryView(state: SummaryFixtures.fourRibbons) }
#Preview("Four ribbons · dark") { LifeSummaryView(state: SummaryFixtures.fourRibbons).previewDark() }
#Preview("Four ribbons · AX3") { LifeSummaryView(state: SummaryFixtures.fourRibbons).previewLargeType() }
#Preview("Loading · light") { LifeSummaryView(state: Fixtures.Summary.loading) }
#Preview("Loading · dark") { LifeSummaryView(state: Fixtures.Summary.loading).previewDark() }
#Preview("Loading · AX3") { LifeSummaryView(state: Fixtures.Summary.loading).previewLargeType() }
#Preview("Error · light") { LifeSummaryView(state: Fixtures.Summary.error) }
#Preview("Error · dark") { LifeSummaryView(state: Fixtures.Summary.error).previewDark() }
#Preview("Error · AX3") { LifeSummaryView(state: Fixtures.Summary.error).previewLargeType() }
