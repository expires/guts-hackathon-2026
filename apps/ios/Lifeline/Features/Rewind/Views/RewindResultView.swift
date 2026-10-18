// Rebuilt for ADR 0026 by W7.
import SwiftUI

/// After a rewind: the life you left next to the life you are back in.
struct RewindResultView: View {
    let state: RewindResultViewState
    var onContinue: () -> Void = {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                HStack(spacing: Theme.Spacing.m) {
                    LLIconImage(.rewind, size: 32)
                    Text("Rewound").font(.llTitle).accessibilityAddTraits(.isHeader)
                }
                Text(state.message).font(.llBody)
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .top, spacing: Theme.Spacing.m) { left; right }
                        .fixedSize(horizontal: false, vertical: true)
                    VStack(spacing: Theme.Spacing.m) { left; right }
                        .fixedSize(horizontal: false, vertical: true)
                }
                Button(action: onContinue) {
                    HStack(spacing: 10) {
                        LLIconImage(.age, size: 24)
                        Text("Choose again")
                    }
                }
                .buttonStyle(.main)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .accessibilityIdentifier("rewind.continue")
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    private var left: some View {
        column(title: "The life you left", index: state.abandonedIndex, netWorth: state.abandonedNetWorth, isNew: false)
            .accessibilityIdentifier("rewind.abandoned")
    }

    private var right: some View {
        column(title: L10n.tr("Back to \(String(state.year)) · Age \(state.age)"), index: state.newIndex, netWorth: state.newNetWorth, isNew: true)
            .accessibilityIdentifier("rewind.new")
    }

    private func column(title: String, index: Double, netWorth: Double, isNew: Bool) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(title).font(.llLabelBold).foregroundStyle(isNew ? Theme.Palette.ink : Theme.Palette.muted)
            Text(L10n.tr("INDEX \(Int(index.rounded()))")).font(.llTitle)
                .contentTransition(.numericText(value: index))
            LLAmount(netWorth).font(.llBodyBold)
                .contentTransition(.numericText(value: netWorth))
        }
        .padding(14)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background {
            if isNew {
                Color.clear.inkSurface(HandCut((24, 18, 22, 16), (16, 22, 18, 24)), hero: true)
            } else {
                HandCut((18, 24, 16, 22), (22, 16, 24, 18))
                    .strokeBorder(Theme.Palette.muted, style: StrokeStyle(lineWidth: Theme.outline, dash: [7, 5]))
            }
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Result · light") { RewindResultView(state: Fixtures.Rewind.result) }
#Preview("Result · dark") { RewindResultView(state: Fixtures.Rewind.result).previewDark() }
#Preview("Result · AX3") { RewindResultView(state: Fixtures.Rewind.result).previewLargeType() }
