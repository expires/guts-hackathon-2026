// Draft by W7. Owned by the UI owner from creation. Rebuilt for ADR 0026 (Money-Test.dc.html).
import SwiftUI

/// "Test it": every option of one money move, played through the same past period, side by side.
struct TestItView: View {
    let state: TestItViewState
    var actions: TestItActions = .noop
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: state.title, leading: HeaderSquareButton(kind: .back, identifier: "testit.close", action: actions.onClose)) {
                    if state.isSampleData { DemoDataBadge() }
                }
                switch state.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    content
                }
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    private var content: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            Text(state.intro)
                .font(.llBody)
                .foregroundStyle(Theme.Palette.ink)
            periodRow
            options
            if let hero = state.hero {
                heroCard(hero)
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                if state.hero == nil {
                    Text(state.summary)
                        .font(.llBodyBold)
                        .accessibilityIdentifier("testit.summary")
                }
                Text(state.evidenceSentence)
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                    .accessibilityIdentifier("testit.evidence")
            }
            .foregroundStyle(Theme.Palette.ink)
            buttons
            SourcesFooter(sources: state.sources)
            Text("This replays the past. It is not a promise about the future.")
                .font(.llLabel)
                .foregroundStyle(Theme.Palette.muted)
        }
    }

    /// The period the API played. One selected chip: the contract has one period per test.
    private var periodRow: some View {
        HStack(spacing: Theme.Spacing.s) {
            LLIconImage(.rateRise, size: 24)
            Text(state.periodLabel)
                .font(.llLabelBold)
                .foregroundStyle(Theme.Palette.surface)
                .padding(.horizontal, Theme.Spacing.m)
                .frame(minHeight: 40)
                .inkSurface(HandCut((11, 15, 12, 16), (16, 12, 15, 11)), fill: Theme.Palette.ink, lineWidth: Theme.chipOutline)
            Spacer(minLength: 0)
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Period: \(state.periodLabel). \(state.periodSentence)")
    }

    @ViewBuilder
    private var options: some View {
        if dynamicTypeSize.isAccessibilitySize || state.options.count == 1 {
            VStack(spacing: Theme.Spacing.m) {
                ForEach(Array(state.options.enumerated()), id: \.element.id) { card($0.element, $0.offset) }
            }
        } else if state.options.count == 2 {
            HStack(alignment: .top, spacing: Theme.Spacing.m) {
                ForEach(Array(state.options.enumerated()), id: \.element.id) { card($0.element, $0.offset).frame(maxHeight: .infinity, alignment: .top) }
            }
            .fixedSize(horizontal: false, vertical: true)
        } else {
            ScrollView(.horizontal) {
                HStack(alignment: .top, spacing: Theme.Spacing.m) {
                    ForEach(Array(state.options.enumerated()), id: \.element.id) { card($0.element, $0.offset).frame(width: 180) }
                }
                .padding(.vertical, Theme.Spacing.xs)
                .padding(.trailing, Theme.Spacing.s)
            }
            .scrollIndicators(.hidden)
        }
    }

    private func card(_ option: TestItViewState.Option, _ offset: Int) -> some View {
        OptionCard(option: option, faceEmoji: state.faceEmoji, shape: offset.isMultiple(of: 2) ? .card : .cardAlt)
    }

    private func heroCard(_ hero: TestItViewState.Hero) -> some View {
        InkCard(shape: .hero, hero: true) {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                ViewThatFits(in: .horizontal) {
                    HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.m) {
                        heroAmount(hero)
                        Text(hero.caption).font(.llLabelBold)
                    }
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        heroAmount(hero)
                        Text(hero.caption).font(.llLabelBold)
                    }
                }
                .accessibilityElement(children: .combine)
                Text(hero.text)
                    .font(.llBody)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("testit.summary")
            }
        }
        .accessibilityIdentifier("testit.hero")
    }

    private func heroAmount(_ hero: TestItViewState.Hero) -> some View {
        Text(hero.amountText)
            .font(.llHero)
            .lineLimit(1)
            .minimumScaleFactor(0.6)
            .contentTransition(.numericText(value: hero.amount))
    }

    private var buttons: some View {
        VStack(spacing: Theme.Spacing.s) {
            if state.canDoThis {
                Button("Do this", action: actions.onDoThis)
                    .buttonStyle(.main)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .accessibilityIdentifier("testit.doThis")
            }
            if let open = state.recommended ?? state.options.first {
                Button { actions.onOpenLife(open.lifeID) } label: {
                    Text("Play it in Life").lineLimit(1).minimumScaleFactor(0.7)
                }
                .buttonStyle(.second)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .accessibilityLabel("Open the \(open.label) life in the Life tab")
                .accessibilityIdentifier("testit.open.\(open.id)")
            }
        }
    }
}

/// One option: face, label, year story, total paid, index.
private struct OptionCard: View {
    let option: TestItViewState.Option
    let faceEmoji: String?
    let shape: HandCut

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            HStack(spacing: Theme.Spacing.s) {
                LLIconImage(LLIcon.face(emoji: faceEmoji), size: 32)
                VStack(alignment: .leading, spacing: 0) {
                    Text(option.label).font(.llBodyBold).fixedSize(horizontal: false, vertical: true)
                    if option.isRecommended {
                        Text("Best here").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                }
            }
            VStack(alignment: .leading, spacing: 10) {
                ForEach(option.yearRows) { row in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(row.title).font(.llLabelBold)
                        Text(row.text).font(.llLabel).fixedSize(horizontal: false, vertical: true)
                        if let change = row.change {
                            Chip(text: change, fill: row.isDown ? Theme.Palette.health : Theme.Palette.money)
                        }
                    }
                    .accessibilityElement(children: .combine)
                }
            }
            .padding(.top, 10)
            .overlay(alignment: .top) { RuleDivider() }
            VStack(alignment: .leading, spacing: 2) {
                Text(option.costLabel).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                Text(Money.format(option.totalCost))
                    .font(.llTitle)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .contentTransition(.numericText(value: option.totalCost))
                HStack(spacing: 6) {
                    LLIconImage(.trophy, size: 24)
                    Text(option.indexLabel).font(.llLabel)
                }
                if option.missedPayments > 0 {
                    Text(TestItViewModel.missedPaymentsText(option.missedPayments))
                        .font(.llLabelBold)
                }
            }
            .padding(.top, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .overlay(alignment: .top) { RuleDivider() }
        }
        .foregroundStyle(Theme.Palette.ink)
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(shape)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(option.accessibilitySummary)
        .accessibilityIdentifier("testit.option.\(option.id)")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Recorded · light") { TestItView(state: TestItFixtures.recorded) }
#Preview("Recorded · dark") { TestItView(state: TestItFixtures.recorded).previewDark() }
#Preview("Ready · light") { TestItView(state: TestItFixtures.ready) }
#Preview("Ready · dark") { TestItView(state: TestItFixtures.ready).previewDark() }
#Preview("Ready · AX3") { TestItView(state: TestItFixtures.ready).previewLargeType() }
#Preview("Sample, 3 options · light") { TestItView(state: TestItFixtures.sampleData) }
#Preview("Sample, 3 options · dark") { TestItView(state: TestItFixtures.sampleData).previewDark() }
#Preview("Sample, 3 options · AX3") { TestItView(state: TestItFixtures.sampleData).previewLargeType() }
#Preview("Mixed sources · light") { TestItView(state: TestItFixtures.mixed) }
#Preview("Mixed sources · dark") { TestItView(state: TestItFixtures.mixed).previewDark() }
#Preview("Mixed sources · AX3") { TestItView(state: TestItFixtures.mixed).previewLargeType() }
#Preview("One option · light") { TestItView(state: TestItFixtures.single) }
#Preview("One option · dark") { TestItView(state: TestItFixtures.single).previewDark() }
#Preview("One option · AX3") { TestItView(state: TestItFixtures.single).previewLargeType() }
#Preview("Loading · light") { TestItView(state: TestItFixtures.loading) }
#Preview("Loading · dark") { TestItView(state: TestItFixtures.loading).previewDark() }
#Preview("Loading · AX3") { TestItView(state: TestItFixtures.loading).previewLargeType() }
#Preview("Offline · light") { TestItView(state: TestItFixtures.offline) }
#Preview("Offline · dark") { TestItView(state: TestItFixtures.offline).previewDark() }
#Preview("Offline · AX3") { TestItView(state: TestItFixtures.offline).previewLargeType() }
#Preview("Not found · light") { TestItView(state: TestItFixtures.notFound) }
#Preview("Not found · dark") { TestItView(state: TestItFixtures.notFound).previewDark() }
#Preview("Not found · AX3") { TestItView(state: TestItFixtures.notFound).previewLargeType() }
