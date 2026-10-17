import Charts
import SwiftUI

/// Your investments: value, split, holdings, "Replay your ISA" and "Possible paths".
struct InvestmentsView: View {
    let state: InvestmentsViewState
    var actions: InvestmentsActions = .noop
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
                        summaryCard
                        if !state.slices.isEmpty { allocationCard }
                        if !state.holdings.isEmpty { holdingsCard }
                        ReplaySection(replay: state.replay, actions: actions)
                        PathsSection(paths: state.paths, actions: actions)
                    }
                }
                .padding(Theme.Spacing.l)
            }
            .animation(Motion.standard(reduceMotion: reduceMotion), value: state)
            .navigationTitle("Your investments")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done", action: actions.onClose)
                        .frame(minWidth: Theme.minTarget, minHeight: Theme.minTarget)
                        .accessibilityIdentifier("investments.done")
                }
            }
        }
    }

    private var summaryCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                Text("Total value").font(.subheadline).foregroundStyle(.secondary)
                Text(Money.format(state.totalValue))
                    .font(.largeTitle.bold().monospacedDigit())
                    .contentTransition(.numericText(value: state.totalValue))
                    .accessibilityLabel("Total value, \(Money.spoken(state.totalValue))")
                HStack {
                    Text("Cash waiting to be invested")
                    Spacer()
                    Text(Money.format(state.cash))
                        .monospacedDigit()
                        .contentTransition(.numericText(value: state.cash))
                }
                .font(.subheadline)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Cash waiting to be invested, \(Money.spoken(state.cash))")
                if state.isSampleData {
                    DemoDataBadge()
                } else {
                    Label(state.dataLabel, systemImage: "bolt.horizontal.circle")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.green)
                }
            }
        }
        .accessibilityIdentifier("investments.summary")
    }

    private var allocationCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text("What it is made of").font(.headline)
                Chart(state.slices) { slice in
                    SectorMark(angle: .value("Share", slice.percent), innerRadius: .ratio(0.6), angularInset: 1.5)
                        .cornerRadius(4)
                        .foregroundStyle(by: .value("Type", slice.label))
                }
                .frame(height: 180)
                .accessibilityLabel("Split of your investments")
                .accessibilityValue(state.slices.map { "\($0.label) \($0.percentText)" }.joined(separator: ", "))
                ForEach(state.slices) { slice in
                    HStack {
                        Text(slice.label)
                        Spacer()
                        Text(slice.percentText).monospacedDigit()
                    }
                    .font(.subheadline)
                    .frame(minHeight: 28)
                    .accessibilityElement(children: .combine)
                }
            }
        }
        .accessibilityIdentifier("investments.allocation")
    }

    private var holdingsCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text("What you own").font(.headline)
                ForEach(state.holdings) { holding in
                    HStack(alignment: .firstTextBaseline) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(holding.name).font(.body)
                            Text(holding.detail).font(.footnote).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Text(Money.format(holding.value)).monospacedDigit()
                    }
                    .frame(minHeight: Theme.minTarget)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("\(holding.name), \(holding.detail), \(Money.spoken(holding.value))")
                }
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
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                HStack {
                    Text("Replay your ISA").font(.headline)
                    Spacer()
                    IllustrativeBadge(text: replay.dataLabel)
                }
                Text("See how different mixes would have done in a real stretch of the past.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)

                if !replay.periods.isEmpty {
                    Picker("Time period", selection: Binding(
                        get: { replay.selectedPeriodID ?? replay.periods[0].id },
                        set: { actions.onSelectPeriod($0) }
                    )) {
                        ForEach(replay.periods) { Text($0.label).tag($0.id) }
                    }
                    .pickerStyle(.menu)
                    .frame(minHeight: Theme.minTarget)
                    .accessibilityIdentifier("replay.period")
                }

                FlowRow(spacing: Theme.Spacing.s) {
                    ForEach(replay.mixes) { mix in
                        let isOn = replay.selectedMixIDs.contains(mix.id)
                        Button {
                            actions.onToggleMix(mix.id)
                        } label: {
                            Label(mix.label, systemImage: isOn ? "checkmark.circle.fill" : "circle")
                                .font(.subheadline.weight(.medium))
                                .padding(.horizontal, Theme.Spacing.m)
                                .frame(minHeight: Theme.minTarget)
                        }
                        .buttonStyle(.glass)
                        .tint(isOn ? .accentColor : nil)
                        .accessibilityAddTraits(isOn ? .isSelected : [])
                        .accessibilityLabel("\(mix.label), \(isOn ? "included" : "not included")")
                        .accessibilityIdentifier("replay.mix.\(mix.id)")
                    }
                }

                Picker("How you pay in", selection: Binding(get: { replay.isMonthly }, set: { actions.onSetMonthly($0) })) {
                    Text("A bit each month").tag(true)
                    Text("All at once").tag(false)
                }
                .pickerStyle(.segmented)
                .frame(minHeight: Theme.minTarget)
                .accessibilityIdentifier("replay.technique")

                switch replay.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetryReplay)
                case .ready:
                    chart
                    ForEach(replay.results) { result in
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            Text(result.label).font(.subheadline.weight(.semibold))
                            Text(result.summary).font(.footnote).foregroundStyle(.secondary)
                            ForEach(result.metrics) { metric in
                                HStack {
                                    Text(metric.label)
                                    Spacer()
                                    Text(metric.value).monospacedDigit()
                                }
                                .font(.subheadline)
                                .frame(minHeight: 28)
                                .accessibilityElement(children: .combine)
                            }
                        }
                        .padding(.top, Theme.Spacing.xs)
                        .accessibilityElement(children: .contain)
                    }
                    Text("\(replay.detailLabel). Made-up numbers shaped like real markets. Not advice.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .accessibilityIdentifier("investments.replay")
    }

    private var chart: some View {
        Chart(replay.points) { point in
            LineMark(x: .value("Month", point.month), y: .value("Index", point.value))
                .foregroundStyle(by: .value("Mix", point.series))
                .interpolationMethod(.monotone)
        }
        .chartYScale(domain: .automatic(includesZero: false))
        .chartXAxisLabel("Months into the period")
        .chartYAxisLabel("Value (start = 100)")
        .frame(height: 220)
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
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                HStack {
                    Text("Possible paths").font(.headline)
                    Spacer()
                    IllustrativeBadge(text: paths.dataLabel)
                }
                switch paths.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetryReplay)
                case .ready:
                    Text(paths.basisText).font(.subheadline).foregroundStyle(.secondary)
                    Chart(paths.points) { point in
                        AreaMark(x: .value("Month", point.month), yStart: .value("Low", point.low), yEnd: .value("High", point.high))
                            .foregroundStyle(Color.accentColor.opacity(0.2))
                            .interpolationMethod(.monotone)
                        LineMark(x: .value("Month", point.month), y: .value("Middle", point.middle))
                            .foregroundStyle(Color.accentColor)
                            .interpolationMethod(.monotone)
                    }
                    .chartYScale(domain: .automatic(includesZero: false))
                    .chartXAxisLabel("Months from now")
                    .chartYAxisLabel("Value (start = 100)")
                    .frame(height: 200)
                    .accessibilityLabel("Fan chart. The line is the middle path. The shaded band covers most paths.")
                    .accessibilityIdentifier("paths.chart")
                }
                // Always visible, in every state.
                Text(paths.disclaimer)
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .accessibilityIdentifier("paths.disclaimer")
            }
        }
        .accessibilityIdentifier("investments.paths")
    }
}

private struct IllustrativeBadge: View {
    let text: String

    var body: some View {
        Label(text, systemImage: "wand.and.stars")
            .font(.caption.weight(.semibold))
            .padding(.horizontal, Theme.Spacing.m)
            .padding(.vertical, Theme.Spacing.xs)
            .glassEffect(.regular.tint(.purple.opacity(0.25)), in: .capsule)
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
