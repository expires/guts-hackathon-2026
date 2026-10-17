import SwiftUI

/// Money tab (handoff A2-Money, theme Paper, card White; then Money-More when scrolled).
/// Order: header, Next Move hero, account tiles, spending, coming up, Guess my spend, then the "More" widgets.
struct MoneyHomeView: View {
    let state: MoneyHomeViewState
    var actions: MoneyHomeActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
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
                    NextMoveCardView(state: state.nextMove, actions: actions.nextMove)
                        .padding(.top, 18)
                    if let moveID = state.nextMove.displayedMove?.id {
                        Button { actions.onAskPenny(moveID) } label: {
                            HStack(spacing: Theme.Spacing.s) {
                                PennyView(mood: .thinking, size: 28)
                                Text("Ask Penny about this move")
                            }
                        }
                        .buttonStyle(.text)
                        .accessibilityIdentifier("money.askPennyMove")
                    }
                    if let budget = state.weeklyBudget {
                        WeeklyBudgetBlock(budget: budget) { actions.nextMove.onFocus(budget.moveID) }
                    }
                    tiles.padding(.top, Theme.Spacing.xs)
                    GuessTeaserCard(state: state.guess, onOpen: actions.onOpenGuess)
                    comingUp
                }
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s).padding(.bottom, Theme.Spacing.m)
        }
        .refreshable { await actions.onRefresh() }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    private var header: some View {
        HStack(spacing: Theme.Spacing.m) {
            LLIconImage(LLIcon.face(emoji: state.header.faceEmoji), size: 40)
            Text(state.header.greeting)
                .font(.llScreenTitle)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityAddTraits(.isHeader)
                .accessibilityIdentifier("money.greeting")
            if state.isSampleData { DataBadge() }
            if state.showsMoney {
                Button { actions.onAskPenny(nil) } label: {
                    PennyView(mood: .smiling, size: 32)
                        .frame(width: Theme.minTarget, height: Theme.minTarget)
                        .inkSurface(HandCut((14, 18, 13, 17)))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Ask Penny")
                .accessibilityIdentifier("money.askPenny")
            }
        }
        .frame(minHeight: 44)
    }

    private var tiles: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            if let tiles = state.tiles {
                Button { actions.onOpenDetail(.accounts) } label: {
                    Tile(shape: .card, title: "In your account", value: tiles.balance, caption: state.paydayText)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("money.balance")
                Button { actions.onOpenDetail(.netWorth) } label: {
                    Tile(shape: .cardAlt, title: "Net worth", value: tiles.netWorth)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("money.netWorth")
            }
        }
    }

    /// "Coming up": at most 3 bills, then "See all" for the full money details.
    private var comingUp: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Coming up").font(.llSection).padding(.bottom, Theme.Spacing.xs)
                .accessibilityAddTraits(.isHeader)
                .accessibilityIdentifier("money.comingUp")
            if state.comingUp.isEmpty {
                Text("No bills in the next 30 days.").font(.llBody).foregroundStyle(Theme.Palette.muted)
            }
            ForEach(state.comingUp) { bill in
                HStack(spacing: Theme.Spacing.m) {
                    Text(bill.shortDateText).font(.llLabel).foregroundStyle(Theme.Palette.muted).frame(width: 48, alignment: .leading)
                    Text(bill.name).font(.llBody).lineLimit(1).frame(maxWidth: .infinity, alignment: .leading)
                    if let chip = bill.priceRiseChip { Chip(text: chip, fill: Theme.Palette.health) }
                    Text(Money.format(bill.amount)).font(.llBodyBold)
                }
                .frame(minHeight: 40)
                .accessibilityElement(children: .combine)
                RuleDivider()
            }
            Button { actions.onOpenDetail(.all) } label: {
                HStack {
                    Text("See all: spending, subscriptions, budgets, goals").font(.llBodyBold).lineLimit(2)
                    Spacer()
                    Chevron()
                }
                .frame(minHeight: Theme.minTarget)
                .contentShape(.rect)
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("money.seeAll")
        }
    }
}

/// Small number tile: label, £ value (24), caption, optional sparkline.
private struct Tile: View {
    let shape: HandCut
    let title: String
    let value: Double
    var caption: String?
    var sparkline: [Double] = []

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(title).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            HStack(spacing: 6) {
                Text(Money.format(value))
                    .font(.llTitle)
                    .contentTransition(.numericText(value: value))
                    .lineLimit(1)
                    .minimumScaleFactor(0.6)
                if sparkline.count > 1 {
                    Sparkline(values: sparkline).frame(width: 48, height: 22)
                }
            }
            if let caption {
                Text(caption).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, Theme.Spacing.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(shape)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(title)
        .accessibilityValue([Money.spoken(value), caption].compactMap { $0 }.joined(separator: ". "))
    }
}

/// Money-green line from the first to the last value.
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

/// Teaser for "Guess my spend" on the Money tab. "Play" opens the full screen.
private struct GuessTeaserCard: View {
    let state: GuessSpendViewState
    let onOpen: () -> Void

    var body: some View {
        HStack(spacing: Theme.Spacing.m) {
            PennyView(mood: .neutral, size: 48)
            VStack(alignment: .leading, spacing: 2) {
                Text("Guess my spend").font(.llSection)
                Text(state.stage == .guessing ? "How much will you spend today?" : (state.reveal?.comparisonText ?? ""))
                    .font(.llLabel)
                if !state.streakText.isEmpty {
                    Text(state.streakText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Button(state.stage == .guessing ? "Play" : "See", action: onOpen)
                .buttonStyle(MainButtonStyle())
                .frame(width: 88)
                .accessibilityIdentifier("guess.play")
        }
        .padding(Theme.Spacing.l)
        .inkSurface(.cardAlt)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("guess.card")
    }
}

/// "Until 2 November: spend up to £82 a week" under the Next Move card. Tapping shows that move in the card.
private struct WeeklyBudgetBlock: View {
    let budget: MoneyHomeViewState.WeeklyBudget
    let onShow: () -> Void

    var body: some View {
        Button(action: onShow) {
            HStack(spacing: Theme.Spacing.m) {
                LLIconImage(.budget, size: 32)
                VStack(alignment: .leading, spacing: 2) {
                    Text(budget.text).font(.llBodyBold).fixedSize(horizontal: false, vertical: true)
                    if let detail = budget.detail {
                        Text(detail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                }
                Spacer(minLength: 0)
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(Theme.Spacing.m)
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .inkSurface(.card, fill: Theme.Palette.money.opacity(0.25))
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier("money.weeklyBudget")
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

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") {
    MoneyHomeView(state: Fixtures.MoneyHome.ready).previewInNavigation()
}

#Preview("Ready · dark") {
    MoneyHomeView(state: Fixtures.MoneyHome.ready).previewInNavigation().previewDark()
}

#Preview("Ready · AX3") {
    MoneyHomeView(state: Fixtures.MoneyHome.ready).previewInNavigation().previewLargeType()
}

#Preview("Revealed · light") {
    MoneyHomeView(state: Fixtures.MoneyHome.revealed).previewInNavigation()
}

#Preview("No data · light") {
    MoneyHomeView(state: Fixtures.MoneyHome.noData).previewInNavigation()
}

#Preview("No data · dark") {
    MoneyHomeView(state: Fixtures.MoneyHome.noData).previewInNavigation().previewDark()
}

#Preview("No data · AX3") {
    MoneyHomeView(state: Fixtures.MoneyHome.noData).previewInNavigation().previewLargeType()
}

#Preview("Loading · light") {
    MoneyHomeView(state: Fixtures.MoneyHome.loading).previewInNavigation()
}

#Preview("Offline · dark") {
    MoneyHomeView(state: Fixtures.MoneyHome.offline).previewInNavigation().previewDark()
}
