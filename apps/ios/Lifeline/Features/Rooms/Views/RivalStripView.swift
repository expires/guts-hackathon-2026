// Rebuilt for ADR 0026 (Play-Live.dc.html rival strip) by W7.
import SwiftUI

/// Live rival strip: one tile per player with face, name, age and INDEX.
struct RivalStripView: View {
    let state: RivalStripViewState
    var caption: String?

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            ScrollView(.horizontal) {
                HStack(spacing: Theme.Spacing.s) {
                    ForEach(state.rivals) { rival in
                        HStack(spacing: 6) {
                            LLIconImage(LLIcon(rawValue: rival.face) ?? .faceTeen, size: 24)
                            VStack(alignment: .leading, spacing: 0) {
                                Text(rival.isMe ? "You" : rival.name).font(.llLabelBold).lineLimit(1)
                                Text(detail(rival)).font(.llLabel).lineLimit(1)
                            }
                        }
                        .padding(.horizontal, Theme.Spacing.s)
                        .padding(.vertical, 6)
                        .inkSurface(.badge, fill: rival.isMe ? Theme.Palette.family : Theme.Palette.surface, lineWidth: Theme.chipOutline)
                        .foregroundStyle(rival.isMe ? Theme.Palette.onArea : Theme.Palette.ink)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(spoken(rival))
                        .accessibilityIdentifier("rival.\(rival.id)")
                    }
                }
                .padding(.trailing, 6)
                .padding(.vertical, 2)
            }
            .scrollIndicators(.hidden)
            if let caption {
                Text(caption).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        }
    }

    private func detail(_ rival: RivalStripViewState.Rival) -> String {
        let age = rival.age.map(String.init) ?? "-"
        let index = rival.index.map { String(Int($0.rounded())) } ?? "-"
        return rival.finished ? "Done · \(index)" : "\(age) · \(index)"
    }

    private func spoken(_ rival: RivalStripViewState.Rival) -> String {
        var parts = [rival.isMe ? "You" : rival.name]
        if let age = rival.age { parts.append("age \(age)") }
        if let index = rival.index { parts.append("INDEX \(Int(index.rounded()))") }
        if rival.finished { parts.append("finished") }
        return parts.joined(separator: ", ")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("4 players · light") { RivalStripView(state: RoomsFixtures.live.rivals, caption: RoomsFixtures.live.rivalCaption).padding() }
#Preview("4 players · dark") { RivalStripView(state: RoomsFixtures.live.rivals).padding().previewDark() }
#Preview("4 players · AX3") { RivalStripView(state: Fixtures.Rooms.rivals).padding().previewLargeType() }
