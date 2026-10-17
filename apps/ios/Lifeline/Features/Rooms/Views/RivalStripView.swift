// Rebuilt by W9 from Play-Live.dc.html (rival strip). First draft by W7.
import SwiftUI

/// Live rival strip: one tile per player with face, name, age and INDEX. Your tile is ink-filled.
struct RivalStripView: View {
    let state: RivalStripViewState
    var caption: String?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.llPresentationMode) private var presentation

    private let shapes = [HandCut((12, 15, 11, 14)), HandCut((15, 11, 14, 12)), HandCut((11, 14, 12, 15)), HandCut((14, 12, 15, 11))]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            ScrollView(.horizontal) {
                HStack(spacing: 6) {
                    ForEach(Array(state.rivals.enumerated()), id: \.element.id) { offset, rival in
                        tile(rival, shape: shapes[offset % shapes.count])
                    }
                }
                .padding(.vertical, 2)
                .padding(.trailing, 2)
            }
            .scrollIndicators(.hidden)
            if let caption, !caption.isEmpty {
                Text(caption).font(.llLabel).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private func tile(_ rival: RivalStripViewState.Rival, shape: HandCut) -> some View {
        HStack(spacing: 6) {
            LLIconImage(LLIcon(rawValue: rival.face) ?? .faceTeen, size: 24)
            VStack(alignment: .leading, spacing: 0) {
                Text(rival.isMe ? "You" : rival.name).font(.llLabelBold).lineLimit(1)
                Text(detail(rival)).font(.llLabel).lineLimit(1).monospacedDigit()
                if let worth = rival.netWorth {
                    Text(RoomAmount.compact(worth, presentation: presentation))
                        .font(.llLabel)
                        .lineLimit(1)
                        .contentTransition(.numericText(value: RoomAmount.shown(worth, presentation: presentation)))
                }
            }
        }
        .padding(6)
        .frame(minWidth: 76, alignment: .leading)
        .inkSurface(shape, fill: rival.isMe ? Theme.Palette.ink : Theme.Palette.surface, lineWidth: Theme.chipOutline)
        .foregroundStyle(rival.isMe ? Theme.Palette.surface : Theme.Palette.ink)
        .opacity(rival.isConnected ? 1 : 0.55)
        .animation(Motion.standard(reduceMotion: reduceMotion), value: rival)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(spoken(rival))
        .accessibilityIdentifier("rival.\(rival.id)")
    }

    private func detail(_ rival: RivalStripViewState.Rival) -> String {
        let age = rival.age.map(String.init) ?? "-"
        let index = rival.index.map { String(Int($0.rounded())) } ?? "-"
        if rival.finished { return "Done · \(index)" }
        if !rival.isConnected { return "Away · \(index)" }
        return "\(age) · \(index)"
    }

    private func spoken(_ rival: RivalStripViewState.Rival) -> String {
        var parts = [rival.isMe ? "You" : rival.name]
        if let age = rival.age { parts.append("age \(age)") }
        if let index = rival.index { parts.append("INDEX \(Int(index.rounded()))") }
        if let worth = rival.netWorth { parts.append(RoomAmount.spoken(worth, presentation: presentation)) }
        if rival.finished { parts.append("finished") }
        if !rival.isConnected { parts.append("away") }
        return parts.joined(separator: ", ")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Live · light") { RivalStripView(state: RoomFlowFixtures.liveAge.rivals, caption: RoomFlowFixtures.liveAge.rivalCaption).padding() }
#Preview("Live · dark") { RivalStripView(state: RoomFlowFixtures.liveAge.rivals).padding().previewDark() }
#Preview("Live · AX3") { RivalStripView(state: RoomFlowFixtures.liveAge.rivals).padding().previewLargeType() }
#Preview("Demo · light") { RivalStripView(state: Fixtures.Rooms.rivals).padding() }
