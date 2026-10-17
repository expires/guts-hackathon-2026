// Draft by W7. Owned by the UI owner from creation.
import Charts
import SwiftUI

/// "Test it": every option of one money move, played through the same past period, side by side.
struct TestItView: View {
    let state: TestItViewState
    var actions: TestItActions = .noop
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        NavigationStack {
            ScrollView {
                switch state.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    content
                }
            }
            .navigationTitle(state.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close", action: actions.onClose)
                        .accessibilityIdentifier("testit.close")
                }
            }
        }
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                if state.isSampleData { DemoDataBadge() }
                Text(state.periodLabel)
                    .font(.headline)
                    .foregroundStyle(.secondary)
                Text(state.periodSentence)
                    .font(.subheadline)
            }
            GlassCard {
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Text(state.summary)
                        .font(.title3.weight(.semibold))
                        .accessibilityIdentifier("testit.summary")
                    Text(state.evidenceSentence)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .accessibilityIdentifier("testit.evidence")
                }
            }
            options
            SourcesFooter(sources: state.sources)
            Text("This replays the past. It is not a promise about the future.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding(Theme.Spacing.l)
    }

    @ViewBuilder
    private var options: some View {
        if dynamicTypeSize.isAccessibilitySize {
            VStack(spacing: Theme.Spacing.m) {
                ForEach(state.options) { card(for: $0) }
            }
        } else if state.options.count <= 2 {
            HStack(alignment: .top, spacing: Theme.Spacing.m) {
                ForEach(state.options) { card(for: $0).frame(maxWidth: .infinity) }
            }
        } else {
            ScrollView(.horizontal) {
                HStack(alignment: .top, spacing: Theme.Spacing.m) {
                    ForEach(state.options) { card(for: $0).frame(width: 220) }
                }
                .padding(.vertical, Theme.Spacing.xs)
            }
            .scrollIndicators(.hidden)
        }
    }

    private func card(for option: TestItViewState.Option) -> some View {
        OptionCard(
            option: option,
            chartMin: state.chartMin,
            chartMax: state.chartMax,
            onOpenLife: { actions.onOpenLife(option.lifeID) }
        )
    }
}

/// One option: chart, numbers, "Open in Life".
private struct OptionCard: View {
    let option: TestItViewState.Option
    let chartMin: Double
    let chartMax: Double
    let onOpenLife: () -> Void

    private var tint: Color { option.isRecommended ? .green : .secondary }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            if option.isRecommended {
                Label("Recommended", systemImage: "star.fill")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.green)
            }
            Text(option.label)
                .font(.headline)
                .fixedSize(horizontal: false, vertical: true)
            chart
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                row("End net worth", Money.format(option.endNetWorth), value: option.endNetWorth)
                row("Total paid", Money.format(option.totalCost), value: option.totalCost)
                row("Missed payments", "\(option.missedPayments)", value: Double(option.missedPayments))
                row("Worst year", "\(option.worstYear)", value: Double(option.worstYear))
                row("Index", option.index.formatted(.number.precision(.fractionLength(1))), value: option.index)
            }
            Button(action: onOpenLife) {
                Label("Open in Life", systemImage: "arrow.up.forward.app")
                    .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
            }
            .buttonStyle(.glass)
            .accessibilityLabel("Open \(option.label) in Life")
            .accessibilityIdentifier("testit.open.\(option.id)")
        }
        .padding(Theme.Spacing.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .glassEffect(option.isRecommended ? .regular.tint(.green.opacity(0.15)) : .regular, in: .rect(cornerRadius: Theme.cornerRadius))
        .overlay {
            if option.isRecommended {
                RoundedRectangle(cornerRadius: Theme.cornerRadius).strokeBorder(.green, lineWidth: 2)
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("testit.option.\(option.id)")
    }

    private var chart: some View {
        Chart(option.path) { point in
            LineMark(x: .value("Year", point.date, unit: .year), y: .value("Net worth", point.netWorth))
                .foregroundStyle(tint)
                .interpolationMethod(.monotone)
            PointMark(x: .value("Year", point.date, unit: .year), y: .value("Net worth", point.netWorth))
                .foregroundStyle(tint)
                .symbolSize(24)
        }
        .chartYScale(domain: chartMin ... chartMax)
        .chartXAxis {
            AxisMarks(values: .stride(by: .year)) { _ in
                AxisValueLabel(format: .dateTime.year(), centered: true)
            }
        }
        .chartYAxis {
            AxisMarks(position: .leading, values: .automatic(desiredCount: 3)) { value in
                AxisGridLine()
                AxisValueLabel {
                    if let amount = value.as(Double.self) { Text(Money.compact(amount)) }
                }
            }
        }
        .frame(height: 120)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Net worth for \(option.label)")
        .accessibilityValue(option.path.map { "\($0.year): \(Money.spoken($0.netWorth))" }.joined(separator: ", "))
    }

    private func row(_ title: String, _ text: String, value: Double) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack {
                Text(title).foregroundStyle(.secondary)
                Spacer(minLength: Theme.Spacing.xs)
                Text(text).monospacedDigit().contentTransition(.numericText(value: value))
            }
            VStack(alignment: .leading) {
                Text(title).foregroundStyle(.secondary)
                Text(text).monospacedDigit().contentTransition(.numericText(value: value))
            }
        }
        .font(.subheadline)
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") { TestItView(state: TestItFixtures.ready) }
#Preview("Ready · dark") { TestItView(state: TestItFixtures.ready).previewDark() }
#Preview("Ready · AX3") { TestItView(state: TestItFixtures.ready).previewLargeType() }
#Preview("Sample, 3 options · light") { TestItView(state: TestItFixtures.sampleData) }
#Preview("Sample, 3 options · dark") { TestItView(state: TestItFixtures.sampleData).previewDark() }
#Preview("Sample, 3 options · AX3") { TestItView(state: TestItFixtures.sampleData).previewLargeType() }
#Preview("Mixed sources · light") { TestItView(state: TestItFixtures.mixed) }
#Preview("Mixed sources · dark") { TestItView(state: TestItFixtures.mixed).previewDark() }
#Preview("Mixed sources · AX3") { TestItView(state: TestItFixtures.mixed).previewLargeType() }
#Preview("One option · light") { TestItView(state: TestItFixtures.single) }
#Preview("One option · dark") { TestItView(state: TestItFixtures.single).previewDark() }
#Preview("One option · AX3") { TestItView(state: TestItFixtures.single).previewLargeType() }
#Preview("Loading · light") { TestItView(state: TestItFixtures.loading) }
#Preview("Loading · dark") { TestItView(state: TestItFixtures.loading).previewDark() }
#Preview("Loading · AX3") { TestItView(state: TestItFixtures.loading).previewLargeType() }
#Preview("Offline · light") { TestItView(state: TestItFixtures.offline) }
#Preview("Offline · dark") { TestItView(state: TestItFixtures.offline).previewDark() }
#Preview("Offline · AX3") { TestItView(state: TestItFixtures.offline).previewLargeType() }
#Preview("Not found · light") { TestItView(state: TestItFixtures.notFound) }
#Preview("Not found · dark") { TestItView(state: TestItFixtures.notFound).previewDark() }
#Preview("Not found · AX3") { TestItView(state: TestItFixtures.notFound).previewLargeType() }
