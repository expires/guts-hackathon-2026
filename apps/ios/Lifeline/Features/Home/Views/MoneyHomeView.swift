import SwiftUI

/// Money tab (ADR 0072, canvas 1 and 2). Order: "Hi, <name>", the forecast card, "Where your money goes",
/// "Due before <date>", "One thing that helps", and one line "In your account £X".
/// `state.blocks` sets the order; this View only draws each block. No "Mock data" or "Sample data" tags (B4).
struct MoneyHomeView: View {
    let state: MoneyHomeViewState
    var actions: MoneyHomeActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                header
                switch state.content {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .connect(prompt):
                    ConnectMoneyCard(prompt: prompt, onConnect: actions.onConnectMoney)
                        .padding(.top, Theme.Spacing.s)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: { Task { await actions.onRefresh() } })
                case .ready:
                    ForEach(state.blocks, id: \.self) { block in
                        self.block(block)
                            .accessibilityElement(children: .contain)
                            .accessibilityIdentifier("money.block.\(block.rawValue)")
                    }
                }
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            // Room under the last line for the floating tab bar (G2).
            .padding(.bottom, 112)
        }
        .refreshable { await actions.onRefresh() }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    private var header: some View {
        HStack(spacing: Theme.Spacing.m) {
            LLIconImage(LLIcon.face(emoji: state.header.faceEmoji), size: 44)
            Text(state.header.greeting)
                .font(ForecastFont.screenTitle)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityAddTraits(.isHeader)
                .accessibilityIdentifier("money.greeting")
            if state.showsMoney {
                Button(action: actions.onAskPenny) {
                    PennyView(mood: .smiling, size: 30)
                        .frame(width: 48, height: 48)
                        .inkSurface(HandCut((14, 18, 13, 17)))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Ask Penny")
                .accessibilityIdentifier("money.askPenny")
            }
        }
        .foregroundStyle(Theme.Palette.ink)
        .frame(minHeight: 48)
    }

    @ViewBuilder
    private func block(_ block: MoneyHomeViewState.Block) -> some View {
        switch block {
        case .forecast:
            switch (state.forecastPhase, state.forecast) {
            case let (_, card?):
                ForecastCardView(state: card, onSeeMaths: actions.onSeeMaths, onAskPenny: actions.onAskPennyForecast, onSources: actions.onSources)
            case let (.failed(error), nil):
                ErrorStateView(state: error, onRetry: actions.onRetryForecast)
            default:
                ForecastCardSkeleton()
            }
        case .spending:
            WhereMoneyGoes(phase: state.spendingPhase, pie: state.spending, actions: actions)
        case .due:
            if let due = state.due { DueBlock(due: due) }
        case .help:
            if let help = state.help { HelpBlock(help: help) }
        case .accountLine:
            if let text = state.accountLineText {
                Text(text)
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                    .monospacedDigit()
                    .frame(maxWidth: .infinity)
                    .padding(.top, 4)
                    .accessibilityIdentifier("money.accountLine")
            }
        }
    }
}

/// "Where your money goes": pie and the top 5 categories this month, then "See all spending".
private struct WhereMoneyGoes: View {
    let phase: LoadPhase
    let pie: SpendingPieState?
    let actions: MoneyHomeActions
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            ForecastSectionTitle(title: L10n.tr("Where your money goes"), trailing: pie?.periodText)
            ForecastCard(spacing: 10) {
                if let pie {
                    if pie.slices.isEmpty {
                        Text("No spending this month yet.").font(ForecastFont.body).foregroundStyle(Theme.Palette.muted)
                    } else {
                        let layout = typeSize.isAccessibilitySize
                            ? AnyLayout(VStackLayout(alignment: .leading, spacing: 16))
                            : AnyLayout(HStackLayout(alignment: .center, spacing: 16))
                        layout {
                            SpendingDonut(
                                slices: pie.slices, totalText: pie.totalText, caption: pie.centerCaption,
                                label: L10n.tr("Spending by category, \(pie.periodText)")
                            )
                            VStack(alignment: .leading, spacing: 0) {
                                ForEach(pie.top) { slice in
                                    Button { actions.onCategory(slice.id, slice.label) } label: {
                                        HStack(spacing: 8) {
                                            CategoryDot(color: ForecastPalette.slice(slice.colorIndex))
                                            Text(slice.label).font(ForecastFont.row).lineLimit(1).frame(maxWidth: .infinity, alignment: .leading)
                                            Text(slice.amountText).font(ForecastFont.rowBold).monospacedDigit()
                                        }
                                        .frame(minHeight: 28)
                                        .contentShape(.rect)
                                    }
                                    .buttonStyle(.plain)
                                    .accessibilityLabel("\(slice.label), \(slice.amountText)")
                                    .accessibilityIdentifier("money.category.\(slice.id)")
                                }
                            }
                        }
                    }
                    RuleDivider()
                    ForecastLinkRow(title: L10n.tr("See all spending"), identifier: "money.seeAllSpending", action: actions.onSeeAllSpending)
                } else if case let .failed(error) = phase {
                    ErrorStateView(state: error, onRetry: actions.onRetrySpending)
                } else {
                    HStack(spacing: 16) {
                        LLSkeleton(.circle(diameter: 132))
                        VStack(spacing: 10) { ForEach(0..<5, id: \.self) { _ in LLSkeleton(.line()) } }
                    }
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("Loading")
                }
            }
        }
    }
}

/// "Due before 2 November": the bills in the forecast, with dates.
private struct DueBlock: View {
    let due: ForecastDueState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            ForecastSectionTitle(title: due.title, trailing: due.totalText)
            ForecastCard(spacing: 10) {
                if due.rows.isEmpty {
                    Text("No bills before your next money.").font(ForecastFont.body).foregroundStyle(Theme.Palette.muted)
                }
                ForEach(due.rows) { row in
                    ViewThatFits(in: .horizontal) {
                        HStack {
                            Text(row.name).frame(maxWidth: .infinity, alignment: .leading)
                            Text(row.dateText).foregroundStyle(Theme.Palette.muted)
                            Text("·").foregroundStyle(Theme.Palette.muted)
                            Text(row.amountText).font(ForecastFont.bodyBold).monospacedDigit()
                        }
                        VStack(alignment: .leading, spacing: 2) {
                            Text(row.name)
                            HStack {
                                Text(row.dateText).foregroundStyle(Theme.Palette.muted)
                                Spacer()
                                Text(row.amountText).font(ForecastFont.bodyBold)
                            }
                        }
                    }
                    .font(ForecastFont.body)
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }
}

/// "One thing that helps": the forecast's one suggestion.
private struct HelpBlock: View {
    let help: ForecastHelpState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            ForecastSectionTitle(title: L10n.tr("One thing that helps"))
            VStack(alignment: .leading, spacing: 8) {
                Text(help.title).font(.custom(LLFont.bodyBold, size: 16, relativeTo: .body)).fixedSize(horizontal: false, vertical: true)
                if let detail = help.detail {
                    Text(detail).font(ForecastFont.row).fixedSize(horizontal: false, vertical: true)
                }
            }
            .foregroundStyle(Theme.Palette.onArea)
            .padding(Theme.Spacing.l)
            .frame(maxWidth: .infinity, alignment: .leading)
            .inkSurface(.card, fill: help.kind == .save ? Color(hex: 0xD5EEDD) : Color(hex: 0xFBE3C2))
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("money.help")
        }
    }
}

/// The one empty state when there is no money data: the prompt and "Connect your money".
private struct ConnectMoneyCard: View {
    let prompt: String
    let onConnect: @MainActor () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            Text(prompt)
                .font(.llTitle)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("money.connectPrompt")
            PrimaryButton(title: "Connect your money") { onConnect() }
                .accessibilityIdentifier("money.connect")
        }
        .padding(Theme.Spacing.xl)
        .frame(maxWidth: .infinity, alignment: .leading)
        .foregroundStyle(Theme.Palette.ink)
        .inkSurface(.hero, hero: true)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("money.connectCard")
    }
}

/// Money-green line from the first to the last value. Used by the older money details view.
struct Sparkline: View {
    let values: [Double]

    var body: some View {
        GeometryReader { proxy in
            let low = values.min() ?? 0
            let span = max(1, (values.max() ?? 1) - low)
            Path { path in
                for (index, value) in values.enumerated() {
                    let x = proxy.size.width * CGFloat(index) / CGFloat(max(1, values.count - 1))
                    let y = proxy.size.height * (1 - CGFloat((value - low) / span))
                    index == 0 ? path.move(to: CGPoint(x: x, y: y)) : path.addLine(to: CGPoint(x: x, y: y))
                }
            }
            .stroke(Theme.Palette.money, style: StrokeStyle(lineWidth: 3, lineCap: .round, lineJoin: .round))
        }
        .accessibilityHidden(true)
    }
}

// MARK: - Previews (light, dark, AX3 Dynamic Type)

#Preview("On track · light") {
    MoneyHomeView(state: ForecastFixtures.home(.onTrack)).previewInNavigation()
}

#Preview("On track · dark") {
    MoneyHomeView(state: ForecastFixtures.home(.onTrack)).previewInNavigation().previewDark()
}

#Preview("On track · AX3") {
    MoneyHomeView(state: ForecastFixtures.home(.onTrack)).previewInNavigation().previewLargeType()
}

#Preview("Running short · light") {
    MoneyHomeView(state: ForecastFixtures.home(.short)).previewInNavigation()
}

#Preview("Loading · light") {
    MoneyHomeView(state: ForecastFixtures.homeLoading).previewInNavigation()
}

#Preview("No data · light") {
    MoneyHomeView(state: Fixtures.MoneyHome.noData).previewInNavigation()
}

#Preview("Offline · dark") {
    MoneyHomeView(state: Fixtures.MoneyHome.offline).previewInNavigation().previewDark()
}
