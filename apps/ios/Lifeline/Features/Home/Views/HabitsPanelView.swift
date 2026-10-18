import SwiftUI

/// "Your habits" card on Money home. With a score the whole card opens the stats page; with none it asks
/// the user to connect their money.
struct HabitsPanelView: View {
    let state: HabitsPanelState
    var onOpen: @MainActor () -> Void = {}
    var onConnect: @MainActor () -> Void = {}

    var body: some View {
        switch state.phase {
        case .loading:
            card { skeleton }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(state.accessibilitySummary)
        case .empty:
            card {
                Text(HabitsPanelState.emptyText)
                    .font(ForecastFont.body)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("money.habits.emptyText")
                PrimaryButton(title: L10n.tr("Connect your money")) { onConnect() }
                    .accessibilityIdentifier("money.habits.connect")
            }
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("money.habits")
        case .score:
            Button(action: onOpen) {
                card { scoreBody }
            }
            .buttonStyle(.plain)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(HabitsPanelState.title)
            .accessibilityValue(state.accessibilitySummary)
            .accessibilityHint(L10n.tr("Opens your profile stats"))
            .accessibilityAddTraits(.isButton)
            .accessibilityIdentifier("money.habits")
        }
    }

    private func card<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 18) {
            ForecastSectionTitle(title: HabitsPanelState.title)
            ForecastCard(spacing: 12) { content() }
        }
    }

    @ViewBuilder private var scoreBody: some View {
        if let overall = state.overall {
            HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.s) {
                Text("\(overall)").font(.llHero).contentTransition(.numericText(value: Double(overall)))
                Text("out of 100").font(.llBody).foregroundStyle(Theme.Palette.muted)
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").font(.llLabelBold).foregroundStyle(Theme.Palette.muted)
            }
        }
        ForEach(state.rows) { row in
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(row.label).font(.llLabelBold)
                    Spacer()
                    Text("\(row.value)").font(.llLabelBold.monospacedDigit())
                }
                InkProgressBar(value: Double(row.value) / 100, color: Theme.Palette.money, height: 12)
            }
        }
        Text(HabitsPanelState.caption)
            .font(.llLabel)
            .foregroundStyle(Theme.Palette.muted)
            .fixedSize(horizontal: false, vertical: true)
        if let source = state.sourceText {
            Text(source).font(.llLabelBold).foregroundStyle(Theme.Palette.muted)
        }
    }

    private var skeleton: some View {
        VStack(alignment: .leading, spacing: 10) {
            LLSkeleton(.line())
            LLSkeleton(.line())
            LLSkeleton(.line())
        }
    }
}

#Preview("Score · light") {
    HabitsPanelView(state: HabitsPanelFixtures.score).padding().paperBackground()
}

#Preview("Score · dark · AX3") {
    HabitsPanelView(state: HabitsPanelFixtures.score).padding().paperBackground().previewDark().previewLargeType()
}

#Preview("Sample data") {
    HabitsPanelView(state: HabitsPanelFixtures.sample).padding().paperBackground()
}

#Preview("Empty") {
    HabitsPanelView(state: .empty).padding().paperBackground()
}

#Preview("Loading") {
    HabitsPanelView(state: .loading).padding().paperBackground()
}

@MainActor enum HabitsPanelFixtures {
    static var score: HabitsPanelState {
        var state = HabitsPanelState.make(MockExamples.habits, meta: nil)
        state.sourceText = L10n.tr("From Monzo")
        return state
    }

    static var sample: HabitsPanelState {
        var state = HabitsPanelState.make(MockExamples.habits, meta: nil)
        state.sourceText = L10n.tr("Sample data")
        return state
    }
}
