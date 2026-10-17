// Rebuilt by W9 from Play-End.dc.html (ADR 0026, 0029). First draft by W7.
import SwiftUI

/// End of a Same Life room: winner, INDEX against the autopilot line, net worth, ribbons,
/// where the lives split, and what you earned.
struct RoomResultView: View {
    let state: RoomResultViewState
    var actions: RoomResultActions = .noop
    @Environment(\.llPresentationMode) private var presentation

    /// Bar scale from the design: 70 at the left edge, 160 at the right, so 100 sits at one third.
    private let low = 70.0
    private let high = 160.0

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                HStack(alignment: .top, spacing: Theme.Spacing.m) {
                    HeaderSquareButton(kind: .close, identifier: "roomResult.close", action: actions.onClose)
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Room results").font(.llTitle).accessibilityAddTraits(.isHeader)
                        if !state.subtitle.isEmpty {
                            Text(state.subtitle).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    if state.isSampleData { DemoDataBadge() }
                }
                if let connection = state.connection {
                    RoomConnectionBanner(state: connection)
                }
                winner
                if let quick = state.quickLife { QuickLifeCard(state: quick) }
                ranking
                if !state.pendingText.isEmpty {
                    Text(state.pendingText)
                        .font(.llLabelBold)
                        .foregroundStyle(Theme.Palette.muted)
                        .accessibilityIdentifier("roomResult.pending")
                }
                splits
                earned
                buttons
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    private var winner: some View {
        HStack(spacing: 14) {
            LLIconImage(.trophy, size: 64)
            VStack(alignment: .leading, spacing: 2) {
                Text(state.pendingText.isEmpty ? "Winner" : "Leader").llEyebrow()
                Text(state.winnerLine.isEmpty ? state.winnerName : state.winnerLine).font(.llTitle)
                    .lineLimit(1).minimumScaleFactor(0.7)
                if !state.winnerNote.isEmpty {
                    Text(state.winnerNote).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                if let worth = state.winnerNetWorth {
                    HStack(spacing: 4) {
                        Text("Net worth")
                        LLAmount(worth)
                    }
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("roomResult.winnerNetWorth")
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(Theme.Spacing.l)
        .inkSurface(.hero, hero: true)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("roomResult.winner")
    }

    private var ranking: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            HStack(alignment: .firstTextBaseline) {
                Text("INDEX vs autopilot").font(.llBodyBold)
                Spacer()
                Text("Line = autopilot 100").font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
            ForEach(Array(state.rows.enumerated()), id: \.element.id) { offset, row in
                if offset > 0 { RuleDivider() }
                HStack(spacing: 10) {
                    Text("\(row.rank)").font(.llLabelBold).frame(width: 16)
                    LLIconImage(LLIcon(rawValue: row.face) ?? .faceTeen, size: 32)
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 6) {
                            Text(row.isMe ? "You" : row.name).font(.llLabelBold).lineLimit(1)
                            Spacer(minLength: 4)
                            if row.note.isEmpty {
                                LLAmount(row.netWorth, style: .compact).font(.llLabel).foregroundStyle(Theme.Palette.muted).lineLimit(1)
                            } else {
                                Text(row.note).font(.llLabel).foregroundStyle(Theme.Palette.muted).lineLimit(1)
                            }
                        }
                        bar(row)
                        if row.ribbonsKnown, row.ribbons > 0 {
                            HStack(spacing: 4) {
                                LLIconImage(.ribbon, size: 24)
                                Text(row.ribbons == 1 ? "1 ribbon" : "\(row.ribbons) ribbons").font(.llLabel)
                            }
                        }
                    }
                    Text("\(Int(row.index.rounded()))")
                        .font(.llBodyBold)
                        .frame(width: 40, alignment: .trailing)
                        .contentTransition(.numericText(value: row.index))
                }
                .padding(.vertical, 6)
                .opacity(row.finished ? 1 : 0.7)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(spoken(row))
                .accessibilityIdentifier("roomResult.row.\(row.id)")
            }
        }
    }

    @ViewBuilder
    private var splits: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            BlockTitle(text: "Where your lives split")
            if state.splits.isEmpty {
                Text(state.splitsNote.isEmpty ? "No split points yet." : state.splitsNote)
                    .font(.llBody)
                    .foregroundStyle(Theme.Palette.muted)
                    .accessibilityIdentifier("roomResult.splitsNote")
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(state.splits.enumerated()), id: \.element.id) { offset, split in
                        if offset > 0 { RuleDivider() }
                        VStack(alignment: .leading, spacing: 4) {
                            Text("\(String(split.year)) · Age \(split.age)").font(.llLabelBold).foregroundStyle(Theme.Palette.muted)
                            Text("You: \(split.myChoice)").font(.llBody).fixedSize(horizontal: false, vertical: true)
                            Text("\(split.rivalName): \(split.rivalChoice)").font(.llBody).fixedSize(horizontal: false, vertical: true)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, Theme.Spacing.l)
                        .padding(.vertical, Theme.Spacing.m)
                        .accessibilityElement(children: .combine)
                        .accessibilityIdentifier("roomResult.split.\(split.id)")
                    }
                }
                .inkSurface(.card)
            }
        }
    }

    @ViewBuilder
    private var earned: some View {
        if !state.earned.isEmpty {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                BlockTitle(text: "You earned")
                FlowRow(spacing: Theme.Spacing.l) {
                    ForEach(state.earned) { item in
                        HStack(spacing: Theme.Spacing.s) {
                            LLIconImage(LLIcon(rawValue: item.icon) ?? .ribbon, size: 32)
                            Text(item.text).font(.llLabel)
                        }
                    }
                }
            }
        }
    }

    private var buttons: some View {
        HStack(spacing: Theme.Spacing.s) {
            Button(action: actions.onPlayAgain) { Text("Rematch").lineLimit(1) }
                .buttonStyle(.main)
                .accessibilityIdentifier("roomResult.rematch")
            ShareLink(item: state.shareText.isEmpty ? state.winnerName : state.shareText) {
                Text("Share results").lineLimit(1).minimumScaleFactor(0.7)
            }
            .buttonStyle(.second)
            .accessibilityIdentifier("roomResult.share")
        }
    }

    /// INDEX bar with an ink tick at the autopilot line (100).
    private func bar(_ row: RoomResultViewState.Row) -> some View {
        GeometryReader { proxy in
            let width = proxy.size.width
            ZStack(alignment: .leading) {
                InkProgressBar(value: (row.index - low) / (high - low), color: row.index >= 100 ? Theme.Palette.money : Theme.Palette.health, height: 12)
                Rectangle()
                    .fill(Theme.Palette.ink)
                    .frame(width: 3, height: 12)
                    .offset(x: width * (100 - low) / (high - low) - 1.5)
            }
        }
        .frame(height: 12)
    }

    private func spoken(_ row: RoomResultViewState.Row) -> String {
        var parts = ["\(row.rank). \(row.isMe ? "You" : row.name)", "INDEX \(Int(row.index.rounded()))", RoomAmount.spoken(row.netWorth, presentation: presentation)]
        if row.ribbonsKnown { parts.append(row.ribbons == 1 ? "1 ribbon" : "\(row.ribbons) ribbons") }
        if !row.finished { parts.append("still playing") }
        return parts.joined(separator: ", ")
    }
}

/// Quick Life summary: INDEX, game net worth, ribbons and the habit score (ratios, 0 to 100).
struct QuickLifeCard: View {
    let state: QuickLifeCardState

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Text(state.title).font(.llBodyBold).accessibilityAddTraits(.isHeader)
            HStack(spacing: Theme.Spacing.l) {
                stat(value: "\(Int(state.index.rounded()))", label: "INDEX")
                VStack(alignment: .leading, spacing: 0) {
                    LLAmount(state.gameNetWorth, style: .compact).font(.llTitle).lineLimit(1).minimumScaleFactor(0.7)
                    Text("Game net worth").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                stat(value: "\(state.ribbons)", label: state.ribbons == 1 ? "Ribbon" : "Ribbons")
            }
            HStack(spacing: Theme.Spacing.s) {
                Text("Habit score").font(.llLabelBold)
                Spacer()
                Text(state.habitOverall.map { "\($0) of 100" } ?? "Not available yet")
                    .font(.llBodyBold)
                    .accessibilityIdentifier("quickLife.habit")
            }
            ForEach(state.habits) { habit in
                HStack(spacing: Theme.Spacing.s) {
                    Text(habit.label).font(.llLabel).frame(width: 130, alignment: .leading)
                    InkProgressBar(value: Double(habit.value) / 100, color: Theme.Palette.money, height: 12)
                    Text("\(habit.value)").font(.llLabelBold).frame(width: 32, alignment: .trailing)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(habit.label) \(habit.value) out of 100")
            }
        }
        .padding(Theme.Spacing.l)
        .inkSurface(.cardAlt)
        .accessibilityIdentifier("quickLife.card")
    }

    private func stat(value: String, label: String) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(value).font(.llTitle)
            Text(label).font(.llLabel).foregroundStyle(Theme.Palette.muted)
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Final · light") { RoomResultView(state: RoomFlowFixtures.resultFinal) }
#Preview("Final · dark") { RoomResultView(state: RoomFlowFixtures.resultFinal).previewDark() }
#Preview("Final · AX3") { RoomResultView(state: RoomFlowFixtures.resultFinal).previewLargeType() }
#Preview("Quick Life · light") { RoomResultView(state: RoomFlowFixtures.resultQuickLife) }
#Preview("Quick Life · dark") { RoomResultView(state: RoomFlowFixtures.resultQuickLife).previewDark() }
#Preview("Pending · light") { RoomResultView(state: RoomFlowFixtures.resultPending) }
#Preview("Pending · dark") { RoomResultView(state: RoomFlowFixtures.resultPending).previewDark() }
#Preview("Demo result · light") { RoomResultView(state: RoomsFixtures.result) }
