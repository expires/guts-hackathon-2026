import Charts
import SwiftUI

/// Colours for chart series and slices, in a fixed order. Series are also named in text, never colour alone.
private let seriesPalette: [Color] = [
    Theme.Palette.work, Theme.Palette.money, Theme.Palette.home, Theme.Palette.family, Theme.Palette.health,
]

/// Your investments: value, split, holdings, "Replay your ISA" and "Possible paths".
struct InvestmentsView: View {
    let state: InvestmentsViewState
    var actions: InvestmentsActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        SheetContainer(title: "Your investments", closeIdentifier: "investments.done", onClose: actions.onClose) {
            switch state.phase {
            case let .loading(loading):
                LoadingStateView(state: loading)
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                summaryCard
                if !state.slices.isEmpty { allocationCard }
                if !state.holdings.isEmpty { holdingsCard }
                ReplaySection(replay: state.replay, actions: actions)
                PathsSection(paths: state.paths, actions: actions)
            }
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: state)
        .background(Theme.Palette.paper)
    }

    private var summaryCard: some View {
        InkCard(shape: .hero, hero: true, padding: Theme.Spacing.xl) {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                Text("Total value").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                Text(Money.format(state.totalValue))
                    .font(.llHero)
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                    .contentTransition(.numericText(value: state.totalValue))
                    .accessibilityLabel("Total value, \(Money.spoken(state.totalValue))")
                HStack {
                    Text("Cash waiting to be invested")
                    Spacer()
                    Text(Money.format(state.cash))
                        .font(.llBodyBold.monospacedDigit())
                        .contentTransition(.numericText(value: state.cash))
                }
                .font(.llBody)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Cash waiting to be invested, \(Money.spoken(state.cash))")
                if state.isSampleData {
                    DemoDataBadge()
                } else {
                    Chip(text: state.dataLabel, fill: Theme.Palette.money)
                }
            }
        }
        .padding(.trailing, Theme.heroShadow.width)
        .padding(.bottom, Theme.heroShadow.height)
        .accessibilityIdentifier("investments.summary")
    }

    private var allocationCard: some View {
        InkCard(shape: .cardAlt) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text("What it is made of").font(.llBodyBold)
                Chart(Array(state.slices.enumerated()), id: \.element.id) { offset, slice in
                    SectorMark(angle: .value("Share", slice.percent), innerRadius: .ratio(0.6), angularInset: 2)
                        .foregroundStyle(seriesPalette[offset % seriesPalette.count])
                }
                .frame(height: 180)
                .accessibilityLabel("Split of your investments")
                .accessibilityValue(state.slices.map { "\($0.label) \($0.percentText)" }.joined(separator: ", "))
                ForEach(Array(state.slices.enumerated()), id: \.element.id) { offset, slice in
                    HStack(spacing: Theme.Spacing.s) {
                        RoundedRectangle(cornerRadius: 3)
                            .fill(seriesPalette[offset % seriesPalette.count])
                            .strokeBorder(Theme.Palette.ink, lineWidth: 2)
                            .frame(width: 10, height: 10)
                            .accessibilityHidden(true)
                        Text(slice.label).font(.llBody)
                        Spacer()
                        Text(slice.percentText).font(.llBodyBold.monospacedDigit())
                    }
                    .frame(minHeight: 28)
                    .accessibilityElement(children: .combine)
                }
            }
        }
        .accessibilityIdentifier("investments.allocation")
    }

    private var holdingsCard: some View {
        RowGroup(title: "What you own") {
            ForEach(state.holdings) { holding in
                ListRow(
                    icon: .investment, title: holding.name, subtitle: holding.detail,
                    trailing: Money.format(holding.value), showsChevron: false
                )
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(holding.name), \(holding.detail), \(Money.spoken(holding.value))")
            }
        }
        .accessibilityIdentifier("investments.holdings")
    }
}

// MARK: - Replay

private struct ReplaySection: View {
    let replay: InvestmentsViewState.Replay
    let actions: InvestmentsActions

    var body: some View {
        InkCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                HStack(alignment: .firstTextBaseline) {
                    Text("Replay your ISA").font(.llBodyBold)
                    Spacer()
                    IllustrativeBadge(text: replay.dataLabel)
                }
                Text("See how different mixes would have done in a real stretch of the past.")
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)

                if !replay.periods.isEmpty {
                    LLChoiceChips(
                        title: "Time period",
                        options: replay.periods.map { .init(id: $0.id, label: $0.label) },
                        selection: replay.selectedPeriodID ?? replay.periods[0].id,
                        identifier: "replay.period",
                        onSelect: actions.onSelectPeriod
                    )
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Text("Mixes to compare").font(.llLabelBold)
                    FlowRow(spacing: Theme.Spacing.s) {
                        ForEach(replay.mixes) { mix in
                            let isOn = replay.selectedMixIDs.contains(mix.id)
                            Button {
                                actions.onToggleMix(mix.id)
                            } label: {
                                HStack(spacing: 6) {
                                    if isOn { LLIconImage(.check, size: 24) }
                                    Text(mix.label).font(.llLabelBold)
                                }
                                .lineLimit(1)
                                .foregroundStyle(isOn ? Theme.Palette.surface : Theme.Palette.ink)
                                .padding(.horizontal, Theme.Spacing.m)
                                .frame(minHeight: Theme.minTarget)
                                .inkSurface(
                                    HandCut((10, 13, 9, 12)),
                                    fill: isOn ? Theme.Palette.ink : Theme.Palette.surface,
                                    lineWidth: Theme.chipOutline
                                )
                            }
                            .buttonStyle(.plain)
                            .accessibilityAddTraits(isOn ? .isSelected : [])
                            .accessibilityLabel("\(mix.label), \(isOn ? "included" : "not included")")
                            .accessibilityIdentifier("replay.mix.\(mix.id)")
                        }
                    }
                }

                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Text("How you pay in").font(.llLabelBold)
                    LLSegmented(
                        options: [.init(id: "monthly", label: "A bit each month"), .init(id: "once", label: "All at once")],
                        selection: replay.isMonthly ? "monthly" : "once"
                    ) { actions.onSetMonthly($0 == "monthly") }
                    .accessibilityIdentifier("replay.technique")
                }

                switch replay.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetryReplay)
                case .ready:
                    chart
                    ForEach(replay.results) { result in
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            Text(result.label).font(.llBodyBold)
                            Text(result.summary).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                            ForEach(result.metrics) { metric in
                                HStack {
                                    Text(metric.label).font(.llBody)
                                    Spacer()
                                    Text(metric.value).font(.llBodyBold.monospacedDigit())
                                }
                                .frame(minHeight: 28)
                                .accessibilityElement(children: .combine)
                            }
                        }
                        .padding(.top, Theme.Spacing.xs)
                        .accessibilityElement(children: .contain)
                    }
                    Text("\(replay.detailLabel). Made-up numbers shaped like real markets. Not advice.")
                        .font(.llLabel)
                        .foregroundStyle(Theme.Palette.muted)
                }
            }
        }
        .accessibilityIdentifier("investments.replay")
    }

    private var chart: some View {
        Chart(replay.points) { point in
            LineMark(x: .value("Month", point.month), y: .value("Index", point.value))
                .foregroundStyle(by: .value("Mix", point.series))
                .lineStyle(StrokeStyle(lineWidth: 3, lineCap: .round, lineJoin: .round))
                .interpolationMethod(.monotone)
        }
        .chartForegroundStyleScale(range: seriesPalette)
        .chartYScale(domain: .automatic(includesZero: false))
        .chartXAxisLabel("Months into the period")
        .chartYAxisLabel("Value (start = 100)")
        .chartYAxis { AxisMarks { _ in AxisGridLine().foregroundStyle(Theme.Palette.rule); AxisValueLabel().font(.llLabel) } }
        .chartXAxis { AxisMarks { _ in AxisValueLabel().font(.llLabel) } }
        .chartLegend(position: .bottom, alignment: .leading)
        .frame(height: 240)
        .accessibilityLabel("Line chart. Each line is one mix, starting at 100.")
        .accessibilityValue(replay.results.map { "\($0.label): \($0.summary)" }.joined(separator: " "))
        .accessibilityIdentifier("replay.chart")
    }
}

// MARK: - Possible paths

private struct PathsSection: View {
    let paths: InvestmentsViewState.Paths
    let actions: InvestmentsActions

    var body: some View {
        InkCard(shape: .cardAlt) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                HStack(alignment: .firstTextBaseline) {
                    Text("Possible paths").font(.llBodyBold)
                    Spacer()
                    IllustrativeBadge(text: paths.dataLabel)
                }
                switch paths.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetryReplay)
                case .ready:
                    Text(paths.basisText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    Chart(paths.points) { point in
                        AreaMark(x: .value("Month", point.month), yStart: .value("Low", point.low), yEnd: .value("High", point.high))
                            .foregroundStyle(Theme.Palette.work.opacity(0.3))
                            .interpolationMethod(.monotone)
                        LineMark(x: .value("Month", point.month), y: .value("Middle", point.middle))
                            .foregroundStyle(Theme.Palette.work)
                            .lineStyle(StrokeStyle(lineWidth: 3, lineCap: .round, lineJoin: .round))
                            .interpolationMethod(.monotone)
                    }
                    .chartYScale(domain: .automatic(includesZero: false))
                    .chartXAxisLabel("Months from now")
                    .chartYAxisLabel("Value (start = 100)")
                    .chartYAxis { AxisMarks { _ in AxisGridLine().foregroundStyle(Theme.Palette.rule); AxisValueLabel().font(.llLabel) } }
                    .chartXAxis { AxisMarks { _ in AxisValueLabel().font(.llLabel) } }
                    .frame(height: 200)
                    .accessibilityLabel("Fan chart. The line is the middle path. The shaded band covers most paths.")
                    .accessibilityIdentifier("paths.chart")
                }
                // Always visible, in every state.
                Text(paths.disclaimer)
                    .font(.llLabelBold)
                    .foregroundStyle(Theme.Palette.muted)
                    .accessibilityIdentifier("paths.disclaimer")
            }
        }
        .accessibilityIdentifier("investments.paths")
    }
}

private struct IllustrativeBadge: View {
    let text: String

    var body: some View {
        Chip(text: text, fill: Theme.Palette.family)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(text). Made-up numbers, not real market data.")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Sample · light") { InvestmentsView(state: Fixtures.Investments.sample) }
#Preview("Sample · dark") { InvestmentsView(state: Fixtures.Investments.sample).previewDark() }
#Preview("Sample · AX3") { InvestmentsView(state: Fixtures.Investments.sample).previewLargeType() }

#Preview("Live · light") { InvestmentsView(state: Fixtures.Investments.live) }
#Preview("Live · dark") { InvestmentsView(state: Fixtures.Investments.live).previewDark() }

#Preview("Replaying · light") { InvestmentsView(state: Fixtures.Investments.replaying) }
#Preview("Loading · light") { InvestmentsView(state: Fixtures.Investments.loading) }
#Preview("Error · light") { InvestmentsView(state: Fixtures.Investments.error) }
