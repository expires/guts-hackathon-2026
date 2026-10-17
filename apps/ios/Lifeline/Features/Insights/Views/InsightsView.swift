import Charts
import SwiftUI

/// Insights (Money tab): what stands out in plain words, then the numbers behind it.
/// Order: sentences (hero), income and spending by month, where your money goes, top shops,
/// subscriptions, unusual payments, spending patterns.
struct InsightsView: View {
    let state: InsightsViewState
    var actions: InsightsActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(
                    title: "Insights",
                    leading: HeaderSquareButton(kind: .back, identifier: "insights.back", action: actions.onClose)
                ) {
                    if state.isSampleData && !state.phase.isLoading { DemoDataBadge() }
                }
                windowPicker
                switch state.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    if state.hasNoHistory {
                        noHistory
                    } else {
                        content
                    }
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: state)
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    // MARK: Window

    private var windowPicker: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            LLSegmented(
                options: InsightsViewState.windowOptions.map { .init(id: "\($0)", label: "\($0) months") },
                selection: "\(state.selectedMonths)"
            ) { id in
                if let months = Int(id) { actions.onSelectMonths(months) }
            }
            .accessibilityIdentifier("insights.window")
            if let note = state.note {
                Label(note, icon: .why)
                    .font(.llLabelBold)
                    .accessibilityIdentifier("insights.note")
            } else if !state.windowText.isEmpty {
                Text(state.windowText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        }
    }

    private var noHistory: some View {
        InkCard(shape: .cardAlt) {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                Text("Not enough history yet").font(.llBodyBold)
                Text("We need at least 2 full months of spending to show insights. Check back soon.")
                    .font(.llBody).foregroundStyle(Theme.Palette.muted)
            }
        }
        .accessibilityIdentifier("insights.empty")
    }

    // MARK: Content

    @ViewBuilder
    private var content: some View {
        hero
        monthsCard
        if !state.categories.isEmpty { categoriesCard }
        if !state.merchants.isEmpty { merchantsCard }
        subscriptionsCard
        if !state.unusual.isEmpty { unusualCard }
        if let patterns = state.patterns { patternsCard(patterns) }
    }

    private var hero: some View {
        InkCard(shape: .hero, hero: true, padding: Theme.Spacing.xl) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text("What stands out").llEyebrow().foregroundStyle(Theme.Palette.muted)
                    .accessibilityAddTraits(.isHeader)
                ForEach(Array(state.sentences.enumerated()), id: \.offset) { offset, sentence in
                    if offset == 0 {
                        Text(sentence).font(.llTitle).fixedSize(horizontal: false, vertical: true)
                    } else {
                        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.s) {
                            Swatch(color: Theme.Palette.money)
                            Text(sentence).font(.llBody).fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
            }
        }
        .padding(.trailing, Theme.heroShadow.width)
        .padding(.bottom, Theme.heroShadow.height)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("insights.hero")
    }

    private var monthsCard: some View {
        InkCard(shape: .cardAlt) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text("Money in and out").font(.llBodyBold).accessibilityAddTraits(.isHeader)
                HStack(spacing: Theme.Spacing.l) {
                    total(title: "Earned", value: state.earnedText, color: Theme.Palette.money)
                    total(title: "Spent", value: state.spentText, color: Theme.Palette.home)
                }
                Chart {
                    ForEach(state.months) { month in
                        BarMark(x: .value("Month", month.label), y: .value("£", month.income), width: .fixed(barWidth))
                            .position(by: .value("Type", "Earned"), axis: .horizontal, span: .ratio(1))
                            .foregroundStyle(Theme.Palette.money)
                            .cornerRadius(3)
                        BarMark(x: .value("Month", month.label), y: .value("£", month.spend), width: .fixed(barWidth))
                            .position(by: .value("Type", "Spent"), axis: .horizontal, span: .ratio(1))
                            .foregroundStyle(Theme.Palette.home)
                            .cornerRadius(3)
                    }
                }
                .chartXAxis {
                    AxisMarks { _ in AxisValueLabel().font(.llLabel).foregroundStyle(Theme.Palette.muted) }
                }
                .chartYAxis {
                    AxisMarks(position: .leading) { value in
                        AxisGridLine().foregroundStyle(Theme.Palette.rule)
                        AxisValueLabel {
                            if let amount = value.as(Double.self) {
                                Text(Money.compact(amount)).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                            }
                        }
                    }
                }
                .frame(height: 180)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Money earned and spent each month")
                .accessibilityValue(state.months.map(\.spokenText).joined(separator: ". "))
                .accessibilityIdentifier("insights.monthsChart")
            }
        }
        .accessibilityIdentifier("insights.months")
    }

    private var barWidth: CGFloat { state.months.count > 6 ? 8 : 14 }

    private func total(title: String, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 6) {
                Swatch(color: color)
                Text(title).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
            Text(value).font(.llTitle).lineLimit(1).minimumScaleFactor(0.6)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }

    private var categoriesCard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            BlockTitle(text: "Where your money goes")
            InkCard(padding: 0) {
                VStack(spacing: 0) {
                    shareBar
                        .padding(.horizontal, Theme.Spacing.l)
                        .padding(.vertical, Theme.Spacing.m)
                    ForEach(state.categories) { category in
                        RuleDivider()
                        categoryRow(category)
                    }
                }
            }
            if state.categories.contains(where: { $0.changeText != nil }) {
                Text("Changes compare with the same number of months before.")
                    .font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        }
        .accessibilityIdentifier("insights.categories")
    }

    private var shareBar: some View {
        GeometryReader { proxy in
            HStack(spacing: 0) {
                ForEach(state.categories) { category in
                    Rectangle()
                        .fill((Area(rawValue: category.area) ?? .other).color)
                        .frame(width: max(0, proxy.size.width * CGFloat(category.share)))
                        .overlay(alignment: .trailing) { Rectangle().fill(Theme.Palette.ink).frame(width: 2) }
                }
                Spacer(minLength: 0)
            }
        }
        .frame(height: 20)
        .background(Theme.Palette.surface)
        .clipShape(HandCut.bar)
        .overlay(HandCut.bar.strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Share of spending by category")
        .accessibilityValue(state.categories.map { "\($0.label) \($0.detailText)" }.joined(separator: ", "))
    }

    private func categoryRow(_ category: InsightsViewState.CategoryRow) -> some View {
        HStack(spacing: Theme.Spacing.m) {
            LLIconImage(LLIcon.from(emoji: category.emoji), size: 32)
            VStack(alignment: .leading, spacing: 2) {
                Text(category.label).font(.llBodyBold)
                Text(category.detailText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
            Spacer(minLength: Theme.Spacing.s)
            if category.trend.count > 1 {
                Sparkline(values: category.trend).frame(width: 40, height: 20)
            }
            VStack(alignment: .trailing, spacing: 2) {
                Text(category.amountText).font(.llBodyBold.monospacedDigit())
                if let change = category.changeText {
                    Chip(text: change, fill: category.changeIsUp ? Theme.Palette.health : Theme.Palette.money)
                }
            }
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, Theme.Spacing.s)
        .frame(minHeight: Theme.minTarget)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(category.label)
        .accessibilityValue([category.amountText, category.detailText, category.changeText].compactMap { $0 }.joined(separator: ". "))
    }

    private var merchantsCard: some View {
        RowGroup(title: "Where you spend most") {
            ForEach(state.merchants) { merchant in
                ListRow(
                    icon: LLIcon.from(emoji: merchant.emoji), title: merchant.name, subtitle: merchant.detailText,
                    trailing: merchant.amountText, showsChevron: false
                )
                .accessibilityElement(children: .combine)
            }
        }
        .accessibilityIdentifier("insights.merchants")
    }

    private var subscriptionsCard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            BlockTitle(text: "Subscriptions")
            InkCard(shape: .cardAlt, padding: 0) {
                VStack(spacing: 0) {
                    HStack(spacing: Theme.Spacing.l) {
                        total(title: "A month", value: state.subscriptionsMonthlyText, color: Theme.Palette.family)
                        total(title: "A year", value: state.subscriptionsAnnualText, color: Theme.Palette.family)
                    }
                    .padding(Theme.Spacing.l)
                    if state.subscriptions.isEmpty {
                        RuleDivider()
                        Text("No regular subscriptions found.")
                            .font(.llBody).foregroundStyle(Theme.Palette.muted)
                            .padding(Theme.Spacing.l)
                    }
                    ForEach(state.subscriptions) { item in
                        RuleDivider()
                        ListRow(
                            icon: LLIcon.from(emoji: item.emoji, fallback: .subscriptions), title: item.name,
                            subtitle: item.annualText, trailing: item.monthlyText, showsChevron: false
                        )
                        .padding(.horizontal, Theme.Spacing.l)
                        .accessibilityElement(children: .combine)
                    }
                }
            }
        }
        .accessibilityIdentifier("insights.subscriptions")
    }

    private var unusualCard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            RowGroup(title: "Bigger than usual") {
                ForEach(state.unusual) { item in
                    ListRow(
                        icon: LLIcon.from(emoji: item.emoji), title: item.name, subtitle: item.detailText,
                        trailing: item.amountText, showsChevron: false
                    )
                    .accessibilityElement(children: .combine)
                }
            }
            Text("Payments more than 3 times what you usually pay in that kind of spending.")
                .font(.llLabel).foregroundStyle(Theme.Palette.muted)
        }
        .accessibilityIdentifier("insights.unusual")
    }

    private func patternsCard(_ patterns: InsightsViewState.Patterns) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            BlockTitle(text: "Spending patterns")
            InkCard {
                VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                    if let share = patterns.weekendShare, let text = patterns.weekendText {
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            Text(text).font(.llBodyBold)
                            InkProgressBar(value: share, color: Theme.Palette.family, height: 14)
                                .accessibilityHidden(true)
                            HStack {
                                Text("Weekdays").font(.llLabel)
                                Spacer()
                                Text("Weekends").font(.llLabel)
                            }
                            .foregroundStyle(Theme.Palette.muted)
                        }
                        .accessibilityElement(children: .combine)
                    }
                    Chart(patterns.weekdays) { day in
                        BarMark(x: .value("Day", day.label), y: .value("£", day.amount))
                            .foregroundStyle(day.isBiggest ? Theme.Palette.home : Theme.Palette.other)
                            .cornerRadius(3)
                    }
                    .chartYAxis(.hidden)
                    .chartXAxis { AxisMarks { _ in AxisValueLabel().font(.llLabel).foregroundStyle(Theme.Palette.muted) } }
                    .frame(height: 110)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("Spending by day of the week")
                    .accessibilityValue(patterns.weekdays.map { "\($0.label) \(Money.spoken($0.amount))" }.joined(separator: ", "))
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        fact(patterns.averageDailyText)
                        if let text = patterns.biggestWeekdayText { fact(text) }
                        if let text = patterns.biggestDayText { fact("Biggest single day, \(text)") }
                    }
                }
            }
        }
        .accessibilityIdentifier("insights.patterns")
    }

    private func fact(_ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.s) {
            Swatch(color: Theme.Palette.work)
            Text(text).font(.llBody)
        }
    }
}

/// Small colour square with an ink edge, as in the Money tab legends.
private struct Swatch: View {
    let color: Color

    var body: some View {
        RoundedRectangle(cornerRadius: 3)
            .fill(color)
            .strokeBorder(Theme.Palette.ink, lineWidth: 2)
            .frame(width: 10, height: 10)
            .accessibilityHidden(true)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") { InsightsView(state: Fixtures.Insights.ready).previewInNavigation() }
#Preview("Ready · dark") { InsightsView(state: Fixtures.Insights.ready).previewInNavigation().previewDark() }
#Preview("Ready · AX3") { InsightsView(state: Fixtures.Insights.ready).previewInNavigation().previewLargeType() }
#Preview("With changes · light") { InsightsView(state: Fixtures.Insights.withChanges).previewInNavigation() }
#Preview("Live · light") { InsightsView(state: Fixtures.Insights.live).previewInNavigation() }
#Preview("No history · light") { InsightsView(state: Fixtures.Insights.noHistory).previewInNavigation() }
#Preview("Loading · light") { InsightsView(state: Fixtures.Insights.loading).previewInNavigation() }
#Preview("Error · light") { InsightsView(state: Fixtures.Insights.error).previewInNavigation() }
