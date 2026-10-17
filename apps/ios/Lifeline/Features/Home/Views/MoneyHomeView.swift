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
                if state.connections.isLoaded {
                    if state.connections.anyConnected { accountsRow } else { connectCard }
                }
                NextMoveCardView(state: state.nextMove, actions: actions.nextMove)
                    .padding(.top, 18)
                tiles.padding(.top, Theme.Spacing.xs)
                GuessTeaserCard(state: state.guess, onOpen: actions.onOpenGuess)
                comingUp
                navigationRow(
                    title: "Your investments",
                    detail: state.investmentsLink?.text ?? "See what you own and replay your ISA through the past.",
                    icon: .investment, identifier: "money.investments", action: actions.onOpenInvestments
                )
                navigationRow(
                    title: "Your money habits",
                    detail: "A score for how you save and spend, with a reason for each part.",
                    icon: .check, identifier: "money.habits", action: actions.onOpenHabits
                )
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.vertical, Theme.Spacing.xl)
        }
        .refreshable { await actions.onRefresh() }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    private var header: some View {
        HStack(spacing: Theme.Spacing.m) {
            LLIconImage(LLIcon.face(emoji: state.header.faceEmoji), size: 40)
            Text(state.header.greeting)
                .font(.llTitle)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityAddTraits(.isHeader)
                .accessibilityIdentifier("money.greeting")
            if state.isSampleData {
                DemoDataBadge()
            } else if state.dataStatusText != nil {
                Chip(text: "Live data", fill: Theme.Palette.money)
                    .accessibilityLabel("Live data. From your connected accounts.")
                    .accessibilityIdentifier("money.liveBadge")
            }
        }
        .frame(minHeight: 40)
    }

    private var connectCard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Text("Connect your accounts").font(.llBodyBold)
            Text("Link Monzo and Trading212 to see your own money here. Until then you are looking at sample data.")
                .font(.llLabel).foregroundStyle(Theme.Palette.muted)
            Button("Connect your accounts", action: actions.onOpenAccounts)
                .buttonStyle(MainButtonStyle())
                .accessibilityIdentifier("money.connectAccounts")
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.cardAlt)
        .accessibilityElement(children: .contain)
    }

    private var accountsRow: some View {
        navigationRow(
            title: "Accounts", detail: state.connections.summaryText, icon: .bank,
            identifier: "money.accounts", action: actions.onOpenAccounts
        )
    }

    private func navigationRow(title: String, detail: String, icon: LLIcon, identifier: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.m) {
                LLIconImage(icon, size: 32)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.llBodyBold)
                    Text(detail).font(.llLabel).foregroundStyle(Theme.Palette.muted).multilineTextAlignment(.leading)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Chevron()
            }
            .padding(Theme.Spacing.l)
            .frame(minHeight: Theme.minTarget)
            .contentShape(.rect)
            .inkSurface(.card)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(title). \(detail)")
        .accessibilityIdentifier(identifier)
    }

    private var tiles: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            if let overview = state.widgets.overview.value {
                Button { actions.onOpenDetail(.accounts) } label: {
                    Tile(shape: .card, title: "In your account", value: overview.balance, caption: state.paydayText)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("money.balance")
                Button { actions.onOpenDetail(.netWorth) } label: {
                    Tile(shape: .cardAlt, title: "Net worth", value: overview.netWorth, caption: overview.netWorthChangeText, sparkline: overview.netWorthSeries)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("money.netWorth")
            } else {
                switch state.widgets.overview.phase {
                case let .failed(error): ErrorStateView(state: error, onRetry: actions.widgets.onRetry)
                default: LoadingStateView(state: .standard)
                }
            }
        }
    }

    /// "Coming up": at most 3 bills, then "See all" for the full money details.
    private var comingUp: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Coming up").font(.llBodyBold).padding(.bottom, Theme.Spacing.xs)
            if let bills = state.widgets.bills.value {
                let shown = Array(bills.items.prefix(3))
                if shown.isEmpty {
                    Text("No bills in the next 30 days.").font(.llBody).foregroundStyle(Theme.Palette.muted)
                }
                ForEach(shown) { bill in
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
            } else if case let .failed(error) = state.widgets.bills.phase {
                ErrorStateView(state: error, onRetry: actions.widgets.onRetry)
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
        .accessibilityIdentifier("money.comingUp")
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
                Text("Guess my spend").font(.llBodyBold)
                Text(state.stage == .guessing ? "How much will you spend today?" : (state.reveal?.comparisonText ?? ""))
                    .font(.llLabel)
                Text(state.streakText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
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

#Preview("Loading · light") {
    MoneyHomeView(state: Fixtures.MoneyHome.loading).previewInNavigation()
}

#Preview("Offline · dark") {
    MoneyHomeView(state: Fixtures.MoneyHome.offline).previewInNavigation().previewDark()
}
