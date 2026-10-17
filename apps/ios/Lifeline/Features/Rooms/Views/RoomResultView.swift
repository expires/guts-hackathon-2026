import SwiftUI

/// End of a room: ranking by Index, net worth, ribbons, and where the lives split.
struct RoomResultView: View {
    let state: RoomResultViewState
    var actions: RoomResultActions = .noop

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                    Text("\(state.winnerName) wins").font(.largeTitle.bold())
                    ForEach(state.rows) { row in
                        GlassCard {
                            HStack(spacing: Theme.Spacing.m) {
                                Text("\(row.rank)").font(.title.bold().monospacedDigit()).frame(minWidth: 32)
                                VStack(alignment: .leading) {
                                    Text(row.isMe ? "\(row.name) (you)" : row.name).font(.headline)
                                    Text("\(row.ribbons) ribbons").font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                VStack(alignment: .trailing) {
                                    Text("Index \(Int(row.index.rounded()))").font(.headline.monospacedDigit())
                                    Text(Money.format(row.netWorth)).font(.caption.monospacedDigit())
                                        .foregroundStyle(row.netWorth < 0 ? .red : .secondary)
                                }
                            }
                        }
                        .accessibilityElement(children: .combine)
                        .accessibilityIdentifier("roomResult.row.\(row.id)")
                    }
                    if !state.splits.isEmpty {
                        SectionTitle(text: "Where your lives split")
                        ForEach(state.splits) { split in
                            VStack(alignment: .leading, spacing: 2) {
                                Text("\(String(split.year)), age \(split.age)").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                                Text("You: \(split.myChoice)")
                                Text("\(split.rivalName): \(split.rivalChoice)").foregroundStyle(.secondary)
                            }
                            .accessibilityElement(children: .combine)
                        }
                    }
                    PrimaryButton(title: "Play again", systemImage: "arrow.clockwise", action: actions.onPlayAgain)
                }
                .padding(Theme.Spacing.l)
            }
            .navigationTitle("Results")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close", action: actions.onClose)
                }
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Result · light") {
    RoomResultView(state: Fixtures.Rooms.result)
}

#Preview("Result · dark") {
    RoomResultView(state: Fixtures.Rooms.result).previewDark()
}

#Preview("Result · AX3") {
    RoomResultView(state: Fixtures.Rooms.result).previewLargeType()
}
