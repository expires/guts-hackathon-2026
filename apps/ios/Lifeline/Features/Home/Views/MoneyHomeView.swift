import SwiftUI

/// Money tab (handoff A2-Money, theme Paper, card White). Order (ADR 0070): header, Next Move, weekly budget,
/// spending this month, bills, subscriptions, budgets and savings goals, the account line, Guess my spend.
/// `state.blocks` sets the order; this View only draws each block.
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
                    ForEach(state.blocks, id: \.self) { block in
                        self.block(block)
                            .accessibilityElement(children: .contain)
                            .accessibilityIdentifier("money.block.\(block.rawValue)")
                    }
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

    @ViewBuilder
    private func block(_ block: MoneyHomeViewState.Block) -> some View {
        switch block {
        case .nextMove:
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                NextMoveCardView(state: state.nextMove, actions: actions.nextMove)
                    .padding(.top, 18)
                if let moveID = state.nextMove.displayedMove?.id {
                    Button { actions.onAskPenny(moveID) } label: {
                        HStack(spacing: Theme.Spacing.s) {
                            PennyView(mood: .thinking, size: 28)
                            Text("Ask Penny about this move")
                        }
                        .frame(minHeight: Theme.minTarget)
                    }
                    .buttonStyle(.text)
                    .accessibilityIdentifier("money.askPennyMove")
                }
            }
        case .weeklyBudget:
            if let budget = state.weeklyBudget {
                WeeklyBudgetBlock(budget: budget) { actions.nextMove.onFocus(budget.moveID) }
            }
        case .spending:
            HomeBlock(section: state.widgets.spending, onRetry: actions.widgets.onRetry) { spending in
                SpendingBlock(spending: spending, top: state.topCategories)
            }
        case .bills:
            if state.widgets.bills.value == nil, !state.comingUp.isEmpty {
                // Home's own next bills show at once while the full bills list loads.
                BillsBlock(bills: state.comingUp, total: nil)
            } else {
                HomeBlock(section: state.widgets.bills, onRetry: actions.widgets.onRetry) { bills in
                    BillsBlock(bills: Array(bills.items.prefix(3)), total: bills.totalNext30Days)
                }
            }
        case .subscriptions:
            HomeBlock(section: state.widgets.subscriptions, onRetry: actions.widgets.onRetry) { SubscriptionsBlock(subscriptions: $0) }
        case .budgetsAndGoals:
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                BudgetsGoalsBlock(budgets: state.widgets.budgets, goals: state.widgets.goals, onRetry: actions.widgets.onRetry)
                seeAll
            }
        case .accountLine:
            if let text = state.accountLineText {
                AccountLine(text: text) { actions.onOpenDetail(.netWorth) }
            }
        case .guess:
            GuessTeaserCard(state: state.guess, onOpen: actions.onOpenGuess)
        }
    }

    /// "See all" opens the full money details screen.
    private var seeAll: some View {
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

/// One widget block on Money home: a small skeleton while loading (or nothing cached yet), a calm error, else the content.
private struct HomeBlock<Value: Equatable & Sendable, Content: View>: View {
    let section: WidgetSection<Value>
    let onRetry: @MainActor () -> Void
    @ViewBuilder let content: (Value) -> Content

    var body: some View {
        switch section.phase {
        case .loading:
            SkeletonList(rows: 2).padding(.vertical, Theme.Spacing.s)
        case let .failed(error):
            ErrorStateView(state: error, onRetry: onRetry)
        case .ready:
            if let value = section.value { content(value) }
        }
    }
}

/// Block title with an optional right-hand figure: "Spending this month   £412 in October 2026".
private struct HomeBlockTitle: View {
    let title: LocalizedStringKey
    var trailing: String?

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .firstTextBaseline) {
                Text(title).font(.llSection)
                Spacer(minLength: Theme.Spacing.s)
                if let trailing { Text(trailing).font(.llLabelBold).lineLimit(1) }
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.llSection)
                if let trailing { Text(trailing).font(.llLabelBold) }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isHeader)
    }
}

/// "Spending this month": one category bar, then the top categories (£0 categories never reach here).
private struct SpendingBlock: View {
    let spending: MoneyWidgetsViewState.Spending
    let top: [MoneyWidgetsViewState.Category]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            HomeBlockTitle(title: "Spending this month", trailing: L10n.tr("\(Money.format(spending.total)) in \(spending.monthText)"))
            if spending.categories.isEmpty {
                Text("No spending this month yet.").font(.llBody).foregroundStyle(Theme.Palette.muted)
            } else {
                SpendingBar(categories: spending.categories)
                VStack(spacing: 0) {
                    ForEach(Array(top.enumerated()), id: \.element.id) { offset, category in
                        HStack(spacing: Theme.Spacing.m) {
                            RoundedRectangle(cornerRadius: 3)
                                .fill((Area(rawValue: category.area) ?? .other).color)
                                .strokeBorder(Theme.Palette.ink, lineWidth: 2)
                                .frame(width: 12, height: 12)
                                .accessibilityHidden(true)
                            Text(category.label).font(.llBody).lineLimit(1).frame(maxWidth: .infinity, alignment: .leading)
                            Text(category.shareText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                            Text(Money.format(category.amount)).font(.llBodyBold).monospacedDigit()
                        }
                        .frame(minHeight: 40)
                        .accessibilityElement(children: .combine)
                        if offset < top.count - 1 { RuleDivider() }
                    }
                }
            }
        }
    }
}

/// "Bills, next 30 days": at most 3 bills and the 30-day total.
private struct BillsBlock: View {
    let bills: [MoneyWidgetsViewState.Bill]
    let total: Double?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HomeBlockTitle(title: "Bills, next 30 days", trailing: total.map(Money.format)).padding(.bottom, Theme.Spacing.xs)
            if bills.isEmpty {
                Text("No bills in the next 30 days.").font(.llBody).foregroundStyle(Theme.Palette.muted)
            }
            ForEach(Array(bills.enumerated()), id: \.element.id) { offset, bill in
                HStack(spacing: Theme.Spacing.m) {
                    // Fixed size, so "10月18日" stays on one line.
                    Text(bill.shortDateText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        .lineLimit(1).fixedSize().frame(minWidth: 48, alignment: .leading)
                    Text(bill.name).font(.llBody).lineLimit(1).frame(maxWidth: .infinity, alignment: .leading)
                    if let chip = bill.priceRiseChip { Chip(text: chip, fill: Theme.Palette.health) }
                    Text(Money.format(bill.amount)).font(.llBodyBold).monospacedDigit()
                }
                .frame(minHeight: 40)
                .accessibilityElement(children: .combine)
                if offset < bills.count - 1 { RuleDivider() }
            }
        }
    }
}

/// "Subscriptions": monthly total and count, then at most 3 subscriptions.
private struct SubscriptionsBlock: View {
    let subscriptions: MoneyWidgetsViewState.Subscriptions

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HomeBlockTitle(
                title: "Subscriptions",
                trailing: L10n.tr("\(Money.format(subscriptions.monthlyTotal)) a month · \(subscriptions.countText)")
            )
            .padding(.bottom, Theme.Spacing.xs)
            if subscriptions.items.isEmpty {
                Text("No subscriptions found.").font(.llBody).foregroundStyle(Theme.Palette.muted)
            }
            let items = Array(subscriptions.items.prefix(3))
            ForEach(Array(items.enumerated()), id: \.element.id) { offset, item in
                HStack(spacing: 10) {
                    LLIconImage(LLIcon.from(emoji: item.emoji, fallback: .subscriptions), size: 24)
                    Text(item.merchant).font(.llBody).lineLimit(1).frame(maxWidth: .infinity, alignment: .leading)
                    if let chip = item.priceRiseChip { Chip(text: chip, fill: Theme.Palette.health) }
                    Text(item.monthlyCostText).font(.llBodyBold).monospacedDigit()
                }
                .frame(minHeight: 40)
                .accessibilityElement(children: .combine)
                .accessibilityHint(item.priceRiseText ?? "")
                if offset < items.count - 1 { RuleDivider() }
            }
        }
    }
}

/// "Budgets and savings goals": at most 3 budgets and 2 goals, each with its progress bar.
private struct BudgetsGoalsBlock: View {
    let budgets: WidgetSection<MoneyWidgetsViewState.Budgets>
    let goals: WidgetSection<[MoneyWidgetsViewState.Goal]>
    let onRetry: @MainActor () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HomeBlockTitle(title: "Budgets and savings goals")
            HomeBlock(section: budgets, onRetry: onRetry) { budgets in
                if budgets.items.isEmpty {
                    Text("No budgets set.").font(.llBody).foregroundStyle(Theme.Palette.muted)
                }
                ForEach(budgets.items.prefix(3)) { budget in
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        HStack(alignment: .firstTextBaseline) {
                            Text(budget.label).font(.llLabelBold)
                            Text(budget.statusText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                            Spacer(minLength: Theme.Spacing.s)
                            Text(budget.detailText).font(.llLabel)
                        }
                        InkProgressBar(value: budget.progress, color: (Area(rawValue: budget.area) ?? .other).color, height: 14)
                    }
                    .accessibilityElement(children: .combine)
                }
            }
            HomeBlock(section: goals, onRetry: onRetry) { goals in
                if goals.isEmpty {
                    Text("No savings goals yet.").font(.llBody).foregroundStyle(Theme.Palette.muted)
                }
                ForEach(goals.prefix(2)) { goal in
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        HStack(alignment: .firstTextBaseline) {
                            Text(goal.name).font(.llLabelBold)
                            Spacer(minLength: Theme.Spacing.s)
                            Text(goal.detailText).font(.llLabel)
                        }
                        InkProgressBar(value: goal.progress, color: Theme.Palette.money, height: 14)
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }
}

/// "In your account £1,186 · Net worth £2,040": one compact line. Tapping opens the details screen.
private struct AccountLine: View {
    let text: String
    let onOpen: () -> Void

    var body: some View {
        Button(action: onOpen) {
            HStack(spacing: Theme.Spacing.s) {
                LLIconImage(.bank, size: 24)
                Text(text).font(.llLabelBold).monospacedDigit().fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Chevron()
            }
            .foregroundStyle(Theme.Palette.ink)
            .frame(minHeight: Theme.minTarget)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(text)
        .accessibilityHint("Opens your accounts and net worth")
        .accessibilityIdentifier("money.accountLine")
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
                Text(state.stage == .guessing ? L10n.tr("How much will you spend today?") : (state.reveal?.comparisonText ?? ""))
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
