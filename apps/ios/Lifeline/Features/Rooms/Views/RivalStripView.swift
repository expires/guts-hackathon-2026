import SwiftUI

/// Live rival strip: age, net worth and Index for every player in the room.
struct RivalStripView: View {
    let state: RivalStripViewState

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            GlassEffectContainer(spacing: Theme.Spacing.s) {
                HStack(spacing: Theme.Spacing.s) {
                    ForEach(state.rivals) { rival in
                        VStack(alignment: .leading, spacing: 2) {
                            HStack(spacing: Theme.Spacing.xs) {
                                Text(rival.isMe ? "You" : rival.name).font(.caption.weight(.semibold))
                                if rival.finished {
                                    Image(systemName: "flag.checkered").font(.caption2).accessibilityLabel("Finished")
                                }
                            }
                            Text(rival.age.map { "Age \($0)" } ?? "Not started")
                                .font(.caption2.monospacedDigit())
                                .contentTransition(.numericText(value: Double(rival.age ?? 0)))
                            if let netWorth = rival.netWorth {
                                Text(Money.compact(netWorth))
                                    .font(.caption2.monospacedDigit())
                                    .foregroundStyle(netWorth < 0 ? .red : .secondary)
                            }
                            if let index = rival.index {
                                Text("Index \(Int(index.rounded()))").font(.caption2.monospacedDigit())
                            }
                        }
                        .padding(Theme.Spacing.s)
                        .frame(minWidth: 88, minHeight: Theme.minTarget, alignment: .leading)
                        .glassEffect(rival.isMe ? .regular.tint(.blue.opacity(0.2)) : .regular, in: .rect(cornerRadius: 14))
                        .accessibilityElement(children: .combine)
                        .accessibilityIdentifier("rival.\(rival.id)")
                    }
                }
                .padding(.horizontal, Theme.Spacing.l)
            }
        }
        .accessibilityLabel("Rivals")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("4 players · light") {
    RivalStripView(state: Fixtures.Rooms.rivals)
}

#Preview("4 players · dark") {
    RivalStripView(state: Fixtures.Rooms.rivals).previewDark()
}

#Preview("4 players · AX3") {
    RivalStripView(state: Fixtures.Rooms.rivals).previewLargeType()
}
