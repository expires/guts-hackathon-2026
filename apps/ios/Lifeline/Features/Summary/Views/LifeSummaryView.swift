import Charts
import SwiftUI

/// End of a life: ribbons, final Index, net worth against autopilot, key moments.
struct LifeSummaryView: View {
    let state: LifeSummaryViewState
    var actions: LifeSummaryActions = .noop

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
            .navigationTitle("Life summary")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close", action: actions.onClose)
                }
            }
        }
    }

    private var lifespan: String {
        if let died = state.died { return "\(String(state.born)) to \(String(died)), age \(state.age)" }
        return "Born \(String(state.born)), age \(state.age)"
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            VStack(spacing: Theme.Spacing.xs) {
                Text(state.emoji).font(.system(size: 72)).accessibilityHidden(true)
                Text(state.name).font(.largeTitle.bold())
                Text(lifespan).foregroundStyle(.secondary)
                if let cause = state.causeOfDeath {
                    Text(cause).font(.subheadline).foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity)
            .accessibilityElement(children: .combine)

            GlassCard {
                HStack {
                    VStack(alignment: .leading) {
                        Text("Final Index").font(.subheadline).foregroundStyle(.secondary)
                        Text("\(Int(state.finalIndex.rounded()))").font(.largeTitle.bold().monospacedDigit())
                    }
                    Spacer()
                    VStack(alignment: .trailing) {
                        Text("Net worth").font(.subheadline).foregroundStyle(.secondary)
                        Text(Money.format(state.netWorth)).font(.title2.bold().monospacedDigit())
                        Text("Autopilot: \(Money.format(state.autopilotNetWorth))").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                    }
                }
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("summary.totals")
            }

            if state.timeline.count > 1 {
                GlassCard {
                    Chart(state.timeline) { point in
                        LineMark(x: .value("Year", point.year), y: .value("You", point.netWorth))
                            .foregroundStyle(by: .value("Life", "You"))
                        LineMark(x: .value("Year", point.year), y: .value("Autopilot", point.autopilotNetWorth))
                            .foregroundStyle(by: .value("Life", "Autopilot"))
                    }
                    .frame(height: 180)
                    .accessibilityLabel("Net worth over time, you against autopilot")
                }
            }

            if !state.ribbons.isEmpty {
                SectionTitle(text: "Ribbons")
                ForEach(state.ribbons) { ribbon in
                    HStack(spacing: Theme.Spacing.m) {
                        Text(ribbon.emoji).font(.title).accessibilityHidden(true)
                        VStack(alignment: .leading) {
                            Text(ribbon.title).font(.headline)
                            Text(ribbon.reason).font(.subheadline).foregroundStyle(.secondary)
                        }
                    }
                    .accessibilityElement(children: .combine)
                }
            }

            if !state.keyMoments.isEmpty {
                SectionTitle(text: "Key moments")
                ForEach(state.keyMoments) { moment in
                    HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.m) {
                        Text(moment.emoji).accessibilityHidden(true)
                        Text("\(String(moment.year)), age \(moment.age)").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                        Text(moment.text)
                    }
                    .accessibilityElement(children: .combine)
                }
            }

            Label("\(state.conceptsUnlocked) concepts learned", systemImage: "books.vertical")

            PrimaryButton(title: "Live another life", systemImage: "arrow.clockwise", action: actions.onNewLife)
                .accessibilityIdentifier("summary.newLife")
        }
        .padding(Theme.Spacing.l)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Death · light") {
    LifeSummaryView(state: Fixtures.Summary.death)
}

#Preview("Death · dark") {
    LifeSummaryView(state: Fixtures.Summary.death).previewDark()
}

#Preview("Death · AX3") {
    LifeSummaryView(state: Fixtures.Summary.death).previewLargeType()
}

#Preview("Loading · light") {
    LifeSummaryView(state: Fixtures.Summary.loading)
}

#Preview("Loading · dark") {
    LifeSummaryView(state: Fixtures.Summary.loading).previewDark()
}

#Preview("Loading · AX3") {
    LifeSummaryView(state: Fixtures.Summary.loading).previewLargeType()
}

#Preview("Error · light") {
    LifeSummaryView(state: Fixtures.Summary.error)
}

#Preview("Error · dark") {
    LifeSummaryView(state: Fixtures.Summary.error).previewDark()
}

#Preview("Error · AX3") {
    LifeSummaryView(state: Fixtures.Summary.error).previewLargeType()
}
