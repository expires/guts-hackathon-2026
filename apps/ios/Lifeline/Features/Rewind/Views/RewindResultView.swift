import SwiftUI

/// After a rewind: the life you left next to the life you are back in.
struct RewindResultView: View {
    let state: RewindResultViewState
    var onContinue: () -> Void = {}

    var body: some View {
        VStack(spacing: Theme.Spacing.xl) {
            Text("Rewound").font(.largeTitle.bold())
            Text(state.message).multilineTextAlignment(.center)
            HStack(spacing: Theme.Spacing.m) {
                column(title: "The life you left", index: state.abandonedIndex, netWorth: state.abandonedNetWorth)
                    .accessibilityIdentifier("rewind.abandoned")
                column(title: "Back to \(String(state.year))", index: state.newIndex, netWorth: state.newNetWorth)
                    .accessibilityIdentifier("rewind.new")
            }
            Spacer(minLength: 0)
            PrimaryButton(title: "Choose again", systemImage: "arrow.triangle.branch", action: onContinue)
                .accessibilityIdentifier("rewind.continue")
        }
        .padding(Theme.Spacing.l)
    }

    private func column(title: String, index: Double, netWorth: Double) -> some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                Text(title).font(.subheadline).foregroundStyle(.secondary)
                Text("Index \(Int(index.rounded()))").font(.title2.bold().monospacedDigit())
                Text(Money.format(netWorth)).font(.headline.monospacedDigit())
                    .foregroundStyle(netWorth < 0 ? .red : .primary)
            }
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Result · light") {
    RewindResultView(state: Fixtures.Rewind.result)
}

#Preview("Result · dark") {
    RewindResultView(state: Fixtures.Rewind.result).previewDark()
}

#Preview("Result · AX3") {
    RewindResultView(state: Fixtures.Rewind.result).previewLargeType()
}
