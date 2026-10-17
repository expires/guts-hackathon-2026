// Rebuilt for ADR 0026 (Play-End.dc.html) by W7.
import SwiftUI

/// End of a Same Life room: winner, INDEX against the autopilot line, what you earned.
struct RoomResultView: View {
    let state: RoomResultViewState
    var actions: RoomResultActions = .noop

    private var maxIndex: Double { max(150, (state.rows.map(\.index).max() ?? 100) * 1.1) }

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
                HStack(spacing: Theme.Spacing.l) {
                    LLIconImage(.trophy, size: 64)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Winner").llEyebrow()
                        Text(state.winnerLine.isEmpty ? state.winnerName : state.winnerLine).font(.llTitle)
                            .lineLimit(1).minimumScaleFactor(0.7)
                        if !state.winnerNote.isEmpty { Text(state.winnerNote).font(.llLabel) }
                    }
                }
                .padding(Theme.Spacing.l)
                .frame(maxWidth: .infinity, alignment: .leading)
                .inkSurface(.hero, fill: Theme.Palette.home, hero: true)
                .foregroundStyle(Theme.Palette.onArea)
                .accessibilityElement(children: .combine)

                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    HStack {
                        Text("INDEX vs autopilot").font(.llBodyBold)
                        Spacer()
                        Text("Line = autopilot 100").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                    ForEach(state.rows) { row in
                        HStack(spacing: Theme.Spacing.s) {
                            Text("\(row.rank)").font(.llLabelBold).frame(width: 16)
                            LLIconImage(LLIcon(rawValue: row.face) ?? .faceTeen, size: 32)
                            VStack(alignment: .leading, spacing: 4) {
                                HStack(spacing: 6) {
                                    Text(row.isMe ? "You" : row.name).font(.llBodyBold).lineLimit(1)
                                    Text(row.note).font(.llLabel).foregroundStyle(Theme.Palette.muted).lineLimit(1)
                                }
                                bar(row)
                            }
                            Text("\(Int(row.index.rounded()))").font(.llBodyBold).frame(width: 40, alignment: .trailing)
                        }
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(row.rank). \(row.isMe ? "You" : row.name), INDEX \(Int(row.index.rounded())). \(row.note)")
                        .accessibilityIdentifier("roomResult.row.\(row.id)")
                    }
                }
                .padding(Theme.Spacing.l)
                .inkSurface(.card)

                if !state.earned.isEmpty {
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        BlockTitle(text: "You earned")
                        FlowRow(spacing: Theme.Spacing.s) {
                            ForEach(state.earned) { item in
                                HStack(spacing: 6) {
                                    LLIconImage(LLIcon(rawValue: item.icon) ?? .ribbon, size: 32)
                                    Text(item.text).font(.llLabelBold)
                                }
                                .padding(.horizontal, Theme.Spacing.s)
                                .padding(.vertical, 4)
                                .inkSurface(.badge, lineWidth: Theme.chipOutline)
                            }
                        }
                    }
                }

                HStack(spacing: Theme.Spacing.s) {
                    Button(action: actions.onPlayAgain) { Text("Rematch").lineLimit(1) }
                        .buttonStyle(.main)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .accessibilityIdentifier("roomResult.rematch")
                    ShareLink(item: state.shareText.isEmpty ? state.winnerName : state.shareText) {
                        Text("Share results").lineLimit(1).minimumScaleFactor(0.7)
                    }
                    .buttonStyle(.second)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .accessibilityIdentifier("roomResult.share")
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    /// INDEX bar with an ink tick at the autopilot line (100).
    private func bar(_ row: RoomResultViewState.Row) -> some View {
        GeometryReader { proxy in
            let width = proxy.size.width
            ZStack(alignment: .leading) {
                InkProgressBar(value: row.index / maxIndex, color: row.index >= 100 ? Theme.Palette.money : Theme.Palette.health, height: 14)
                Rectangle()
                    .fill(Theme.Palette.ink)
                    .frame(width: 2, height: 20)
                    .offset(x: width * 100 / maxIndex - 1)
            }
        }
        .frame(height: 20)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Demo result · light") { RoomResultView(state: RoomsFixtures.result) }
#Preview("Demo result · dark") { RoomResultView(state: RoomsFixtures.result).previewDark() }
#Preview("Demo result · AX3") { RoomResultView(state: RoomsFixtures.result).previewLargeType() }
#Preview("Result · light") { RoomResultView(state: Fixtures.Rooms.result) }
