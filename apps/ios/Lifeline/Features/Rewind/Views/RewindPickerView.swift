// Rebuilt for ADR 0026 (Life-Rewind.dc.html) by W7.
import SwiftUI

/// Rewind: choose a past decision, see what you did and what you will try, then replay.
struct RewindPickerView: View {
    let state: RewindPickerViewState
    var actions: RewindActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: "Rewind", icon: .rewind, leading: HeaderSquareButton(kind: .back, identifier: "rewind.close", action: actions.onClose)) {
                    OutlineTag(text: state.allowanceText)
                        .accessibilityIdentifier("rewind.allowance")
                }
                if state.isSampleData { DemoDataBadge() }
                if let selected = state.selected {
                    if state.options.count > 1 { decisionChips }
                    timelineCard(selected)
                    BlockTitle(text: "Same start. Other choice.")
                    compare(selected)
                    indexRow
                    buttons(selected)
                } else {
                    InkCard {
                        Text("No choices yet. Answer an event first.")
                            .font(.llBody)
                            .foregroundStyle(Theme.Palette.muted)
                    }
                    Button("Back to my life", action: actions.onClose).buttonStyle(.second).lineLimit(1).minimumScaleFactor(0.7)
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    /// One chip per past decision. The selected chip is ink.
    private var decisionChips: some View {
        ScrollView(.horizontal) {
            HStack(spacing: Theme.Spacing.s) {
                ForEach(state.options) { option in
                    let isOn = option.id == state.selected?.id
                    Button { actions.onSelect(option.id) } label: {
                        Text(L10n.tr("\(String(option.year)) · Age \(option.age)"))
                            .font(.llLabelBold)
                            .foregroundStyle(isOn ? Theme.Palette.surface : Theme.Palette.ink)
                            .padding(.horizontal, Theme.Spacing.m)
                            .frame(minHeight: Theme.minTarget)
                            .inkSurface(.badge, fill: isOn ? Theme.Palette.ink : Theme.Palette.surface, lineWidth: Theme.chipOutline)
                    }
                    .buttonStyle(.plain)
                    .accessibilityAddTraits(isOn ? .isSelected : [])
                    .accessibilityLabel("\(option.year), age \(option.age). \(option.text)")
                    .accessibilityIdentifier("rewind.select.\(option.id)")
                }
            }
            .padding(.vertical, 2)
        }
        .scrollIndicators(.hidden)
    }

    private func timelineCard(_ selected: RewindPickerViewState.Option) -> some View {
        InkCard(shape: HandCut((18, 24, 16, 22), (22, 16, 24, 18))) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text(L10n.tr("Back to \(String(selected.year)) · Age \(selected.age)")).font(.llBodyBold)
                RewindTimeline(labels: state.timeline)
                Text(L10n.tr("What you learned stays. Money and stats go back to \(String(selected.year))."))
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
            }
        }
    }

    @ViewBuilder
    private func compare(_ selected: RewindPickerViewState.Option) -> some View {
        let did = VStack(alignment: .leading, spacing: 10) {
            Text("What I did").llEyebrow()
            Text(selected.text).font(.llBodyBold).foregroundStyle(Theme.Palette.ink)
            VStack(alignment: .leading, spacing: 2) {
                ForEach(state.didLines, id: \.self) { Text($0) }
            }
            .font(.llLabel)
        }
        .foregroundStyle(Theme.Palette.muted)
        .padding(14)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .overlay {
            HandCut((18, 24, 16, 22), (22, 16, 24, 18))
                .strokeBorder(Theme.Palette.muted, style: StrokeStyle(lineWidth: Theme.outline, dash: [7, 5]))
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("rewind.did")

        let alt = state.alternative
        let tryCard = VStack(alignment: .leading, spacing: 10) {
            Text("What I'll try").llEyebrow()
            Text(alt?.title ?? "The other choice").font(.llBodyBold)
            VStack(alignment: .leading, spacing: 2) {
                ForEach(alt?.lines ?? [], id: \.self) { Text($0).fixedSize(horizontal: false, vertical: true) }
            }
            .font(.llLabel)
            ForEach(alt?.sources ?? []) { SourceChip(source: $0) }
        }
        .padding(14)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .inkSurface(HandCut((24, 18, 22, 16), (16, 22, 18, 24)), hero: true)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("rewind.try")

        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: Theme.Spacing.m) { did; tryCard }
                    .fixedSize(horizontal: false, vertical: true)
                VStack(spacing: Theme.Spacing.m) { did; tryCard }
                    .fixedSize(horizontal: false, vertical: true)
            }
            ForEach(Array(Set((alt?.sources ?? []).compactMap(\.note))).sorted(), id: \.self) { note in
                Label(note, icon: .why)
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                    .accessibilityIdentifier("sourceNote")
            }
        }
    }

    private var indexRow: some View {
        HStack(spacing: Theme.Spacing.m) {
            VStack(alignment: .leading, spacing: 0) {
                Text("Your INDEX now").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                Text("\(Int(state.indexNow.rounded()))").font(.llTitle)
                    .contentTransition(.numericText(value: state.indexNow))
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            VStack(alignment: .leading, spacing: 0) {
                Text("Autopilot twin").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                Text("\(Int(state.autopilotIndex.rounded()))").font(.llTitle)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            if !state.indexGapText.isEmpty {
                Chip(text: state.indexGapText, fill: state.isBehind ? Theme.Palette.health : Theme.Palette.money)
            }
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, Theme.Spacing.m)
        .inkSurface(.card)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("rewind.index")
    }

    @ViewBuilder
    private func buttons(_ selected: RewindPickerViewState.Option) -> some View {
        VStack(spacing: Theme.Spacing.s) {
            if state.needsPass {
                // Penny Plus is cut (ADR 0067): no purchase, just the plain fact.
                Text("No rewinds left in this life.")
                    .font(.llBodyBold)
                    .frame(maxWidth: .infinity, minHeight: Theme.buttonHeight)
                    .accessibilityIdentifier("rewind.noneLeft")
            } else {
                Button { actions.onPick(selected.id) } label: {
                    HStack(spacing: 10) {
                        if state.isSubmitting {
                            ProgressView().tint(Theme.Palette.surface)
                        } else {
                            LLIconImage(.rewind, size: 24)
                        }
                        Text(L10n.tr("Replay from \(String(selected.year))"))
                    }
                }
                .buttonStyle(.main)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .disabled(state.isSubmitting)
                .accessibilityIdentifier("rewind.option.\(selected.id)")
            }
            Button("Keep my real path", action: actions.onClose)
                .buttonStyle(.second)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .accessibilityIdentifier("rewind.keep")
        }
    }
}

/// Dashed line from the rewind point to now: orange handle at the start, small stops, ink dot at "Now".
private struct RewindTimeline: View {
    let labels: [String]

    var body: some View {
        VStack(spacing: 6) {
            GeometryReader { proxy in
                let width = proxy.size.width
                ZStack(alignment: .leading) {
                    Path { p in
                        p.move(to: CGPoint(x: 13, y: 13))
                        p.addLine(to: CGPoint(x: width - 8, y: 13))
                    }
                    .stroke(Theme.Palette.muted, style: StrokeStyle(lineWidth: 3, dash: [6, 5]))
                    ForEach(1..<max(1, labels.count - 1), id: \.self) { index in
                        Circle()
                            .fill(Theme.Palette.surface)
                            .stroke(Theme.Palette.muted, lineWidth: 3)
                            .frame(width: 12, height: 12)
                            .position(x: 13 + (width - 21) * CGFloat(index) / CGFloat(max(1, labels.count - 1)), y: 13)
                    }
                    Circle()
                        .fill(Theme.Palette.ink)
                        .frame(width: 16, height: 16)
                        .position(x: width - 8, y: 13)
                    HandCut((13, 12, 13.5, 12.5))
                        .fill(Theme.Palette.ink)
                        .offset(x: 2, y: 3)
                        .frame(width: 26, height: 26)
                        .position(x: 13, y: 13)
                    HandCut((13, 12, 13.5, 12.5))
                        .fill(Theme.Palette.home)
                        .overlay(HandCut((13, 12, 13.5, 12.5)).strokeBorder(Theme.Palette.ink, lineWidth: 3))
                        .frame(width: 26, height: 26)
                        .position(x: 13, y: 13)
                }
            }
            .frame(height: 26)
            HStack {
                ForEach(Array(labels.enumerated()), id: \.offset) { index, label in
                    if index > 0 { Spacer(minLength: 0) }
                    Text(label).font(index == 0 ? .llLabelBold : .llLabel)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(L10n.tr("Timeline from \(labels.first ?? "") to now. The handle is at \(labels.first ?? "")."))
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Mortgage · light") { RewindPickerView(state: RewindFixtures.mortgage) }
#Preview("Mortgage · dark") { RewindPickerView(state: RewindFixtures.mortgage).previewDark() }
#Preview("Mortgage · AX3") { RewindPickerView(state: RewindFixtures.mortgage).previewLargeType() }
#Preview("Other decision · light") { RewindPickerView(state: RewindFixtures.otherDecision) }
#Preview("Other decision · dark") { RewindPickerView(state: RewindFixtures.otherDecision).previewDark() }
#Preview("Other decision · AX3") { RewindPickerView(state: RewindFixtures.otherDecision).previewLargeType() }
#Preview("Needs pass · light") { RewindPickerView(state: RewindFixtures.needsPass) }
#Preview("Needs pass · dark") { RewindPickerView(state: RewindFixtures.needsPass).previewDark() }
#Preview("Needs pass · AX3") { RewindPickerView(state: RewindFixtures.needsPass).previewLargeType() }
