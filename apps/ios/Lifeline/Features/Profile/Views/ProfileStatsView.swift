import Charts
import SwiftUI

/// "Your profile": a strip of connections, then one card per section. Available sections show their numbers
/// and where they come from; the others say what is missing and jump to the right connect option.
struct ProfileStatsView: View {
    let state: ProfileStatsViewState
    var actions: ProfileStatsActions = .noop
    var title = L10n.tr("Your profile")

    var body: some View {
        VStack(spacing: 0) {
            ScreenHeader(title: title, leading: HeaderSquareButton(kind: .back, identifier: "profile.back", action: actions.onClose))
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.top, Theme.Spacing.s)
                .padding(.bottom, Theme.Spacing.xs)
            switch state.phase {
            case .loading:
                ScrollView { SkeletonList(rows: 5).padding(Theme.Spacing.margin) }
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                ScrollView {
                    VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                        connectionsStrip
                        ForEach(state.sections) { section in
                            SectionCard(section: section, actions: actions)
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.margin)
                    .padding(.top, Theme.Spacing.s)
                    .padding(.bottom, Theme.Spacing.l)
                }
                .scrollIndicators(.hidden)
                .refreshable { await actions.onRefresh() }
                playBar
            }
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    private var connectionsStrip: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            BlockTitle(text: L10n.tr("Where your data comes from"))
            FlowRow(spacing: Theme.Spacing.s) {
                ForEach(state.connections) { badge in
                    Button { actions.onConnect(ConnectKind(rawValue: badge.id)) } label: {
                        HStack(spacing: 6) {
                            Circle()
                                .fill(badge.isConnected ? Theme.Palette.money : Theme.Palette.other)
                                .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: 2))
                                .frame(width: 12, height: 12)
                            Text(badge.title).font(.llLabelBold)
                            Text(badge.statusText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                        .padding(.horizontal, Theme.Spacing.m)
                        .frame(minHeight: Theme.minTarget)
                        .inkSurface(.chip, lineWidth: Theme.chipOutline)
                        .foregroundStyle(Theme.Palette.ink)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel([badge.title, badge.statusText, badge.detail].compactMap { $0 }.joined(separator: ". "))
                    .accessibilityHint(L10n.tr("Opens the connect options"))
                    .accessibilityIdentifier("profile.badge.\(badge.id)")
                }
            }
            .accessibilityElement(children: .contain)
        }
    }

    private var playBar: some View {
        VStack(spacing: Theme.Spacing.xs) {
            if let missing = state.playMissing {
                Text(missing)
                    .font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityIdentifier("profile.playMissing")
            }
            PrimaryButton(title: state.playTitle, icon: .tabPlay, action: actions.onPlay)
                .accessibilityIdentifier("profile.play")
        }
        .padding(.horizontal, Theme.Spacing.margin)
        .padding(.top, Theme.Spacing.s)
        .padding(.bottom, Theme.Spacing.s)
        .background(Theme.Palette.paper)
    }
}

private struct SectionCard: View {
    let section: ProfileStatsViewState.Section
    let actions: ProfileStatsActions

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            HStack(alignment: .firstTextBaseline) {
                Text(section.title).font(.llTitle).accessibilityAddTraits(.isHeader)
                Spacer(minLength: Theme.Spacing.s)
                if let line = section.sourceLine {
                    Text(line).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        .accessibilityIdentifier("profile.source.\(section.id)")
                }
            }
            if section.isAvailable {
                switch section.content {
                case .none: EmptyView()
                case let .habits(overall, rows, caption): HabitsBlock(overall: overall, rows: rows, caption: caption)
                case let .spending(body): SpendingBlock(body: body)
                case let .netWorth(body): NetWorthBlock(body: body)
                case let .investments(body): InvestmentsBlock(body: body)
                }
            } else {
                Text(section.missingHint ?? "").font(.llBody).fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("profile.hint.\(section.id)")
                Button(section.jumpTitle ?? L10n.tr("Connect your money")) { actions.onConnect(section.jump) }
                    .buttonStyle(.second)
                    .accessibilityIdentifier("profile.jump.\(section.id)")
            }
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .foregroundStyle(Theme.Palette.ink)
        .inkSurface(.card, fill: section.isAvailable ? Theme.Palette.surface : Theme.Palette.paper)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("profile.section.\(section.id)")
    }
}

private struct Caption: View {
    let text: String
    var body: some View {
        Text(text).font(.llLabel).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
    }
}

private struct StatLine: View {
    let label: String
    let value: String
    var body: some View {
        HStack {
            Text(label).font(.llBody)
            Spacer(minLength: Theme.Spacing.s)
            Text(value).font(.llBodyBold.monospacedDigit())
        }
        .accessibilityElement(children: .combine)
    }
}

private struct HabitsBlock: View {
    let overall: Int?
    let rows: [ProfileStatsViewState.HabitRow]
    let caption: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            if let overall {
                HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.s) {
                    Text("\(overall)").font(.llHero).contentTransition(.numericText(value: Double(overall)))
                    Text("out of 100").font(.llBody).foregroundStyle(Theme.Palette.muted)
                }
                .accessibilityElement(children: .combine)
                .accessibilityLabel(L10n.tr("Habit score \(overall) out of 100"))
            }
            ForEach(rows) { row in
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(row.label).font(.llLabelBold)
                        Spacer()
                        Text("\(row.value)").font(.llLabelBold.monospacedDigit())
                    }
                    InkProgressBar(value: Double(row.value) / 100, color: Theme.Palette.money, height: 14)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(row.label)
                .accessibilityValue(L10n.tr("\(row.value) out of 100"))
            }
            Caption(text: caption)
        }
    }
}

private struct SpendingBlock: View {
    let body_: ProfileStatsViewState.SpendingBody
    init(body: ProfileStatsViewState.SpendingBody) { body_ = body }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Text(body_.periodText).font(.llLabelBold).foregroundStyle(Theme.Palette.muted)
            HStack(spacing: Theme.Spacing.l) {
                if let inText = body_.inText { Text(inText).font(.llTitle).foregroundStyle(Theme.Palette.ink) }
                Text(body_.outText).font(.llTitle)
            }
            if let average = body_.averageText { Caption(text: average) }
            if !body_.categories.isEmpty {
                Chart(Array(body_.categories.enumerated()), id: \.element.id) { offset, category in
                    BarMark(x: .value("Pounds", category.amount), y: .value("Category", category.label))
                        .foregroundStyle(ForecastPalette.slice(offset))
                        .cornerRadius(4)
                        .annotation(position: .trailing) {
                            Text(category.amountText).font(.llLabelBold.monospacedDigit())
                        }
                }
                .chartXAxis(.hidden)
                .chartYAxis {
                    AxisMarks { _ in AxisValueLabel().font(.llLabel) }
                }
                .chartXScale(range: .plotDimension(endPadding: 56))
                .frame(height: CGFloat(body_.categories.count) * 48 + 8)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(L10n.tr("Spending by category"))
                .accessibilityValue(body_.categories.map { "\($0.label) \($0.amountText), \($0.shareText)" }.joined(separator: ". "))
                .accessibilityIdentifier("profile.spendingChart")
            }
            StatLine(label: L10n.tr("Subscriptions"), value: body_.subscriptionsText)
            Caption(text: body_.caption)
        }
    }
}

private struct NetWorthBlock: View {
    let body_: ProfileStatsViewState.NetWorthBody
    init(body: ProfileStatsViewState.NetWorthBody) { body_ = body }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            Text(body_.totalText).font(.llHero).accessibilityIdentifier("profile.netWorth.total")
            StatLine(label: L10n.tr("Cash"), value: body_.cashText)
            StatLine(label: L10n.tr("Investments"), value: body_.investmentsText)
            if let other = body_.otherText { StatLine(label: L10n.tr("Everything else"), value: other) }
            RuleDivider()
            ForEach(body_.parts) { part in
                HStack {
                    Text(part.label).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    Spacer(minLength: Theme.Spacing.s)
                    Text(part.amountText).font(.llLabel.monospacedDigit()).foregroundStyle(Theme.Palette.muted)
                }
                .accessibilityElement(children: .combine)
            }
            Caption(text: body_.caption)
        }
    }
}

private struct InvestmentsBlock: View {
    let body_: ProfileStatsViewState.InvestmentsBody
    init(body: ProfileStatsViewState.InvestmentsBody) { body_ = body }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Text(body_.totalText).font(.llHero).accessibilityIdentifier("profile.investments.total")
            HStack {
                Text(body_.countText).font(.llBodyBold)
                if let invested = body_.investedText {
                    Text(L10n.tr("\(invested) invested")).font(.llBody).foregroundStyle(Theme.Palette.muted)
                }
            }
            if let note = body_.note { Caption(text: note) }
            if !body_.mix.isEmpty {
                Chart(body_.mix) { slice in
                    SectorMark(angle: .value("Value", slice.value), innerRadius: .ratio(0.55), angularInset: 1)
                        .foregroundStyle(ForecastPalette.slice(slice.colorIndex))
                }
                .chartLegend(.hidden)
                .frame(width: 168, height: 168)
                .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: 2.5))
                .frame(maxWidth: .infinity)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(L10n.tr("Investment mix"))
                .accessibilityValue(body_.mix.map { "\($0.label) \($0.shareText)" }.joined(separator: ". "))
                .accessibilityIdentifier("profile.mixChart")
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    ForEach(body_.mix) { slice in
                        HStack(spacing: Theme.Spacing.s) {
                            CategoryDot(color: ForecastPalette.slice(slice.colorIndex))
                            Text(slice.label).font(.llBody)
                            Spacer(minLength: Theme.Spacing.s)
                            Text(slice.valueText).font(.llBodyBold.monospacedDigit())
                            Text(slice.shareText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                .frame(minWidth: 40, alignment: .trailing)
                        }
                        .accessibilityElement(children: .combine)
                    }
                }
                Caption(text: body_.caption)
            }
            if !body_.holdings.isEmpty {
                BlockTitle(text: L10n.tr("What you're invested in"))
                ForEach(body_.holdings) { holding in
                    HStack {
                        VStack(alignment: .leading, spacing: 0) {
                            Text(holding.name).font(.llBody).lineLimit(2)
                            if let detail = holding.detail { Text(detail).font(.llLabel).foregroundStyle(Theme.Palette.muted) }
                        }
                        Spacer(minLength: Theme.Spacing.s)
                        Text(holding.valueText).font(.llBodyBold.monospacedDigit())
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }
}

// MARK: - Previews

#Preview("Trading 212 only · light") { ProfileStatsView(state: ProfileStatsPreviews.t212Only) }
#Preview("Full · light") { ProfileStatsView(state: ProfileStatsPreviews.full) }
#Preview("Full · dark") { ProfileStatsView(state: ProfileStatsPreviews.full).previewDark() }
#Preview("Full · AX3") { ProfileStatsView(state: ProfileStatsPreviews.full).previewLargeType() }
#Preview("Sample student · light") { ProfileStatsView(state: ProfileStatsPreviews.sample) }
#Preview("Nothing connected · light") { ProfileStatsView(state: ProfileStatsPreviews.nothing) }
#Preview("Loading · light") { ProfileStatsView(state: ProfileStatsViewState()) }
