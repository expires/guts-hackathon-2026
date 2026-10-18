import SwiftUI

/// "All spending" (B3.5, canvas 4): month switch, large pie, every category with its share and change,
/// then rent and bills apart.
struct AllSpendingView: View {
    let state: AllSpendingState
    var actions: AllSpendingActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                ForecastScreenHeader(title: L10n.tr("All spending"), identifier: "spending.back", onBack: actions.onBack)
                if let pie = state.pie {
                    monthSwitch(pie)
                    SpendingDonut(
                        slices: pie.slices, totalText: pie.totalText, caption: pie.centerCaption, size: 196, ring: 30,
                        label: L10n.tr("Spending by category, \(pie.periodText)")
                    )
                    .frame(maxWidth: .infinity)
                    if pie.slices.isEmpty {
                        Text("No spending this month yet.").font(ForecastFont.body).foregroundStyle(Theme.Palette.muted)
                    } else {
                        categoryList(pie.slices, showsShare: true)
                    }
                    if !pie.fixed.isEmpty {
                        ForecastSectionTitle(title: L10n.tr("Rent and bills"))
                        categoryList(pie.fixed, showsShare: false)
                    }
                    if let note = state.fixedNote {
                        Text(note).font(.llLabel).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
                    }
                } else {
                    switch state.phase {
                    case let .failed(error): ErrorStateView(state: error, onRetry: actions.onRetry)
                    default:
                        LLSkeleton(.block(height: 52))
                        LLSkeleton(.circle(diameter: 196)).frame(maxWidth: .infinity)
                        SkeletonList(rows: 5)
                    }
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s).padding(.bottom, 112)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    private func monthSwitch(_ pie: SpendingPieState) -> some View {
        HStack {
            arrow(.left, label: L10n.tr("Previous month"), enabled: state.canGoBack, id: "spending.previous", action: actions.onPrevious)
            VStack(spacing: 0) {
                Text(pie.monthTitle).font(.custom(LLFont.bodyBold, size: 16, relativeTo: .body))
                    .contentTransition(.numericText())
                Text(pie.rangeText).font(ForecastFont.caption).foregroundStyle(Theme.Palette.muted)
            }
            .frame(maxWidth: .infinity)
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("spending.month")
            arrow(.right, label: L10n.tr("Next month"), enabled: state.canGoForward, id: "spending.next", action: actions.onNext)
        }
        .padding(4)
        .inkSurface(.buttonAlt)
    }

    private func arrow(_ direction: Chevron.Direction, label: String, enabled: Bool, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Chevron(direction: direction)
                .frame(width: Theme.minTarget, height: Theme.minTarget)
                .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.35)
        .accessibilityLabel(label)
        .accessibilityIdentifier(id)
    }

    private func categoryList(_ slices: [SpendingSlice], showsShare: Bool) -> some View {
        VStack(spacing: 0) {
            ForEach(Array(slices.enumerated()), id: \.element.id) { offset, slice in
                if offset > 0 { RuleDivider() }
                Button { actions.onCategory(slice.id) } label: {
                    HStack(spacing: 12) {
                        CategoryDot(color: showsShare ? ForecastPalette.slice(slice.colorIndex) : ForecastPalette.rest)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(slice.label).font(ForecastFont.bodyBold)
                            let detail = [showsShare ? slice.shareText : nil, slice.changeText].compactMap { $0 }.filter { !$0.isEmpty }
                            if !detail.isEmpty {
                                Text(detail.joined(separator: " · ")).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        Text(slice.amountText).font(.custom(LLFont.bodyBold, size: 16, relativeTo: .body)).monospacedDigit()
                        Chevron().scaleEffect(0.8)
                    }
                    .padding(.vertical, 12)
                    .frame(minHeight: Theme.minTarget)
                    .contentShape(.rect)
                }
                .buttonStyle(.plain)
                .accessibilityElement(children: .combine)
                .accessibilityAddTraits(.isButton)
                .accessibilityIdentifier("spending.category.\(slice.id)")
            }
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, 4)
        .foregroundStyle(Theme.Palette.ink)
        .inkSurface(.card)
    }
}

/// One category (B3.6, canvas 5): total, usual monthly amount, bars by week, every payment, Ask Penny.
struct CategoryDetailView: View {
    let state: CategoryDetailState
    var actions: CategoryDetailActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                ForecastScreenHeader(title: state.title, identifier: "category.back", onBack: actions.onBack)
                switch state.phase {
                case .loading:
                    LLSkeleton(.line(width: 0.4, height: 44))
                    SkeletonCard()
                    SkeletonList(rows: 4)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    content
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s).padding(.bottom, 112)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    @ViewBuilder
    private var content: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(state.totalText).font(ForecastFont.total).monospacedDigit()
                Text(state.periodText).font(ForecastFont.body).foregroundStyle(Theme.Palette.muted)
            }
            VStack(alignment: .leading, spacing: 0) {
                Text(state.totalText).font(ForecastFont.total).monospacedDigit()
                Text(state.periodText).font(ForecastFont.body).foregroundStyle(Theme.Palette.muted)
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("category.total")
        if let usual = state.usualText {
            Text(usual).font(ForecastFont.body).padding(.top, -8)
        }
        if !state.bars.isEmpty {
            ForecastCard {
                Text("By week").font(ForecastFont.bodyBold)
                WeekBars(bars: state.bars)
            }
        }
        if !state.payments.isEmpty {
            VStack(spacing: 0) {
                ForEach(Array(state.payments.enumerated()), id: \.element.id) { offset, payment in
                    if offset > 0 { RuleDivider() }
                    HStack(alignment: .firstTextBaseline) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(payment.name).font(ForecastFont.bodyBold)
                            Text(payment.dateText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        Text(payment.amountText).font(ForecastFont.bodyBold).monospacedDigit()
                    }
                    .padding(.vertical, 10)
                    .accessibilityElement(children: .combine)
                }
            }
            .padding(.horizontal, Theme.Spacing.l)
            .padding(.vertical, 4)
            .inkSurface(.card)
            .accessibilityIdentifier("category.payments")
        }
        Button(state.askTitle, action: actions.onAskPenny)
            .buttonStyle(ForecastButtonStyle(filled: false))
            .accessibilityIdentifier("category.askPenny")
    }
}

/// Bars by week, tallest at 90 pt (canvas 5).
private struct WeekBars: View {
    let bars: [CategoryDetailState.Bar]
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        if typeSize.isAccessibilitySize {
            VStack(alignment: .leading, spacing: 8) {
                ForEach(bars) { bar in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(bar.label).font(ForecastFont.caption).foregroundStyle(Theme.Palette.muted)
                            Spacer()
                            Text(bar.amountText).font(.llLabelBold)
                        }
                        GeometryReader { proxy in
                            RoundedRectangle(cornerRadius: 8).fill(Theme.Palette.money)
                                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Theme.Palette.ink, lineWidth: 2))
                                .frame(width: max(8, proxy.size.width * bar.fraction))
                        }
                        .frame(height: 20)
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        } else {
            HStack(alignment: .bottom, spacing: 12) {
                ForEach(bars) { bar in
                    VStack(spacing: 6) {
                        Text(bar.amountText).font(.llLabelBold)
                        RoundedRectangle(cornerRadius: 8).fill(Theme.Palette.money)
                            .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(Theme.Palette.ink, lineWidth: 2))
                            .frame(height: max(8, 90 * bar.fraction))
                        Text(bar.label).font(ForecastFont.caption).foregroundStyle(Theme.Palette.muted)
                            .lineLimit(2).multilineTextAlignment(.center).minimumScaleFactor(0.8)
                    }
                    .frame(maxWidth: .infinity)
                    .accessibilityElement(children: .combine)
                }
            }
            .frame(minHeight: 120, alignment: .bottom)
            .padding(.horizontal, 4)
        }
    }
}

// MARK: - Previews

#Preview("All spending · light") { AllSpendingView(state: ForecastFixtures.allSpending).previewInNavigation() }
#Preview("All spending · dark") { AllSpendingView(state: ForecastFixtures.allSpending).previewInNavigation().previewDark() }
#Preview("All spending · AX3") { AllSpendingView(state: ForecastFixtures.allSpending).previewInNavigation().previewLargeType() }
#Preview("Category · light") { CategoryDetailView(state: ForecastFixtures.category).previewInNavigation() }
#Preview("Category · dark") { CategoryDetailView(state: ForecastFixtures.category).previewInNavigation().previewDark() }
#Preview("Category · AX3") { CategoryDetailView(state: ForecastFixtures.category).previewInNavigation().previewLargeType() }
