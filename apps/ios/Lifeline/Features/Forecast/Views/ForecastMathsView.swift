import SwiftUI

/// "The maths" (B3.3, canvas 3): 4 steps with their sources, the buffer buttons, the sum, habits,
/// "See the detailed breakdown", "What if prices rose like in 2022?" and "Ask Penny about this".
struct ForecastMathsView: View {
    let state: ForecastMathsState
    var actions: ForecastMathsActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                ForecastScreenHeader(title: L10n.tr("The maths"), identifier: "maths.back", onBack: actions.onBack)
                switch state.phase {
                case .loading:
                    SkeletonList(rows: 4, showsCard: true)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    content
                }
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s).padding(.bottom, 112)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    @ViewBuilder
    private var content: some View {
        Text(state.intro).font(ForecastFont.body).foregroundStyle(Theme.Palette.muted)
            .accessibilityIdentifier("maths.intro")
        ForEach(state.steps) { step in
            stepCard(step)
        }
        if let sum = state.sum {
            VStack(alignment: .leading, spacing: 4) {
                Text(sum.line).font(ForecastFont.body)
                Text(sum.result).font(ForecastFont.sum).contentTransition(.numericText()).monospacedDigit()
                    .accessibilityIdentifier("maths.result")
                if let daily = sum.daily {
                    Text(daily).font(ForecastFont.row).foregroundStyle(Theme.Palette.onArea.opacity(0.75))
                }
            }
            .foregroundStyle(Theme.Palette.onArea)
            .padding(Theme.Spacing.l)
            .frame(maxWidth: .infinity, alignment: .leading)
            .inkSurface(.hero, fill: Color(hex: 0xD5EEDD), hero: true)
            .accessibilityElement(children: .combine)
            .padding(.bottom, 4)
        }
        if let habits = state.habits {
            ForecastCard {
                Text("Compared with your habits").font(ForecastFont.bodyBold)
                Text(habits.text).font(ForecastFont.row).fixedSize(horizontal: false, vertical: true)
                if let source = habits.source {
                    Text(source).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
            }
            .accessibilityElement(children: .combine)
        }
        Button(action: actions.onDetail) {
            HStack {
                Text("See the detailed breakdown").font(ForecastFont.bodyBold).frame(maxWidth: .infinity, alignment: .leading)
                Chevron()
            }
            .padding(.horizontal, Theme.Spacing.l)
            .frame(minHeight: 52)
            .foregroundStyle(Theme.Palette.ink)
            .inkSurface(.buttonAlt)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("maths.detail")
        // "What if" questions go to Penny with the forecast loaded (user request, replaces the 2022 button).
        Button(L10n.tr("Ask Penny \u{201C}what if...\u{201D}"), action: actions.onAskWhatIf)
            .buttonStyle(ForecastButtonStyle(filled: false))
            .padding(.top, 8)
            .accessibilityIdentifier("maths.whatIf")
        Button("Ask Penny about this", action: actions.onAskPenny)
            .buttonStyle(ForecastButtonStyle(filled: true, height: 52))
            .accessibilityIdentifier("maths.askPenny")
    }

    private func stepCard(_ step: ForecastMathsState.Step) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text(verbatim: "\(step.number)")
                .font(ForecastFont.bodyBold)
                .foregroundStyle(Theme.Palette.surface)
                .frame(width: 28, height: 28)
                .background(Circle().fill(Theme.Palette.ink))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: step.isBuffer ? 6 : 3) {
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(step.title).frame(maxWidth: .infinity, alignment: .leading)
                        Text(step.amountText).monospacedDigit().contentTransition(.numericText())
                    }
                    VStack(alignment: .leading, spacing: 2) {
                        Text(step.title)
                        Text(step.amountText).monospacedDigit()
                    }
                }
                .font(ForecastFont.bodyBold)
                Text(step.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
                if step.isBuffer, state.hasBudget {
                    bufferButtons
                    if let error = state.bufferError {
                        Text(error).font(.llLabelBold).foregroundStyle(ForecastPalette.runOutText)
                            .accessibilityIdentifier("maths.bufferError")
                    }
                }
            }
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .foregroundStyle(Theme.Palette.ink)
        .inkSurface(.card)
        .accessibilityElement(children: step.isBuffer ? .contain : .combine)
        .accessibilityIdentifier("maths.step.\(step.number)")
    }

    private var bufferButtons: some View {
        FlowRow(spacing: 6) {
            ForEach(ForecastMathsState.bufferOptions, id: \.self) { pct in
                let selected = pct == state.bufferPct
                Button { actions.onBuffer(pct) } label: {
                    Text(verbatim: "\(pct)%")
                        .font(.custom(LLFont.bodyBold, size: 13, relativeTo: .footnote))
                        .foregroundStyle(selected ? Theme.Palette.surface : Theme.Palette.ink)
                        .padding(.horizontal, 12)
                        .frame(minWidth: Theme.minTarget, minHeight: 32)
                        .background(Capsule().fill(selected ? Theme.Palette.ink : Theme.Palette.surface))
                        .overlay(Capsule().strokeBorder(Theme.Palette.ink, lineWidth: 2))
                        .padding(.vertical, 6)
                        .contentShape(.rect)
                }
                .buttonStyle(.plain)
                .disabled(state.isUpdatingBuffer && !selected)
                .accessibilityLabel(L10n.tr("Buffer \(pct) percent"))
                .accessibilityAddTraits(selected ? .isSelected : [])
                .accessibilityIdentifier("maths.buffer.\(pct)")
            }
        }
    }
}

/// "Detailed breakdown" (B3.4, canvas 3b): every line in pence, with the source of each block.
struct ForecastBreakdownView: View {
    let state: ForecastBreakdownState
    var onBack: () -> Void = {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                ForecastScreenHeader(title: L10n.tr("Detailed breakdown"), identifier: "breakdown.back", onBack: onBack)
                Text(state.intro).font(ForecastFont.body).foregroundStyle(Theme.Palette.muted)
                ForEach(state.sections) { section in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(verbatim: "\(section.number). \(section.title)").font(ForecastFont.smallSection)
                            .accessibilityAddTraits(.isHeader)
                        VStack(spacing: 0) {
                            ForEach(section.rows) { row in
                                if row.id > 0 { RuleDivider() }
                                rowView(row)
                            }
                        }
                        .padding(.horizontal, Theme.Spacing.l)
                        .padding(.vertical, 6)
                        .frame(maxWidth: .infinity)
                        .inkSurface(.card)
                        Text(section.source).font(ForecastFont.caption).foregroundStyle(Theme.Palette.muted)
                    }
                    .accessibilityElement(children: .contain)
                    .accessibilityIdentifier("breakdown.section.\(section.number)")
                }
                if let closing = state.closing {
                    Text(closing)
                        .font(ForecastFont.row)
                        .foregroundStyle(Theme.Palette.onArea)
                        .padding(.horizontal, Theme.Spacing.l).padding(.vertical, 14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .inkSurface(.card, fill: state.closingIsGood ? Color(hex: 0xD5EEDD) : Color(hex: 0xFBE3C2))
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s).padding(.bottom, 112)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    private func rowView(_ row: ForecastBreakdownState.Row) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(row.label)
                if let note = row.note {
                    Text(note).font(ForecastFont.caption).foregroundStyle(Theme.Palette.muted)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Text(row.value).monospacedDigit().multilineTextAlignment(.trailing)
        }
        .font(row.isTotal ? ForecastFont.rowBold : ForecastFont.row)
        .padding(.vertical, 9)
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Previews

#Preview("Maths · light") {
    ForecastMathsView(state: .make(ForecastFixtures.forecast(.onTrack))).previewInNavigation()
}

#Preview("Maths · dark") {
    ForecastMathsView(state: .make(ForecastFixtures.forecast(.short, stress: 2022))).previewInNavigation().previewDark()
}

#Preview("Maths · AX3") {
    ForecastMathsView(state: .make(ForecastFixtures.forecast(.onTrack))).previewInNavigation().previewLargeType()
}

#Preview("Breakdown · light") {
    ForecastBreakdownView(state: .make(ForecastFixtures.forecast(.onTrack))).previewInNavigation()
}

#Preview("Breakdown · dark") {
    ForecastBreakdownView(state: .make(ForecastFixtures.forecast(.short))).previewInNavigation().previewDark()
}

#Preview("Breakdown · AX3") {
    ForecastBreakdownView(state: .make(ForecastFixtures.forecast(.onTrack))).previewInNavigation().previewLargeType()
}
