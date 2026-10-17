// Draft by W7. Owned by the UI owner from creation. ADR 0026 (Play-Live.dc.html).
import SwiftUI

/// Live Same Life room: who you are, the rival strip, this year's story, two stats.
struct RoomLiveView: View {
    let state: RoomLiveViewState
    var actions: RoomLiveActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                HStack(spacing: Theme.Spacing.m) {
                    HeaderSquareButton(kind: .back, identifier: "roomLive.leave", action: actions.onLeave)
                    LLIconImage(LLIcon(rawValue: state.face) ?? .facePriya, size: 40)
                        .frame(width: 48, height: 48)
                        .inkSurface(HandCut((18, 22, 17, 21), (21, 17, 22, 18)), fill: Theme.Palette.family)
                    VStack(alignment: .leading, spacing: 0) {
                        Text(state.name).font(.llBodyBold).lineLimit(1)
                        Text(state.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted).lineLimit(1)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    VStack(alignment: .trailing, spacing: 0) {
                        Text(Money.format(state.bank)).font(.llTitle).lineLimit(1).minimumScaleFactor(0.7)
                            .contentTransition(.numericText(value: state.bank))
                        Text("In the bank").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                    .accessibilityElement(children: .combine)
                }
                if state.isSampleData { DemoDataBadge() }
                RivalStripView(state: state.rivals, caption: state.rivalCaption)
                    .padding(Theme.Spacing.m)
                    .inkSurface(.cardAlt)
                InkCard(shape: .hero, hero: true) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        Text(state.storyTitle).font(.llTitle).accessibilityAddTraits(.isHeader)
                        ForEach(state.storyLines, id: \.self) { Text($0).font(.llBody) }
                        Button(action: actions.onOpenLesson) {
                            HStack(spacing: Theme.Spacing.m) {
                                LLIconImage(.lesson, size: 32)
                                VStack(alignment: .leading, spacing: 0) {
                                    Text(state.lessonTitle).font(.llBodyBold)
                                    Text("See what happened and rewind").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                }
                                Spacer(minLength: 0)
                                Chevron()
                            }
                            .padding(Theme.Spacing.m)
                            .frame(minHeight: Theme.minTarget)
                            .inkSurface(.buttonThird, fill: Theme.Palette.paper, lineWidth: Theme.chipOutline)
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("roomLive.lesson")
                    }
                }
                VStack(spacing: Theme.Spacing.m) {
                    ForEach(state.stats) { stat in
                        HStack(spacing: Theme.Spacing.s) {
                            LLIconImage(LLIcon(rawValue: stat.icon) ?? .happiness, size: 24)
                            Text(stat.title).font(.llLabelBold).frame(width: 96, alignment: .leading)
                            InkProgressBar(value: Double(stat.value) / 100, color: stat.id == "money" ? Theme.Palette.money : Theme.Palette.home)
                            Text("\(stat.value)%").font(.llLabelBold).frame(width: 44, alignment: .trailing)
                        }
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(stat.title) \(stat.value) out of 100")
                    }
                }
                Button(action: actions.onFinish) {
                    HStack(spacing: 10) {
                        LLIconImage(.trophy, size: 24)
                        Text("Finish the run").lineLimit(1)
                    }
                }
                .buttonStyle(.main)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .accessibilityIdentifier("roomLive.finish")
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Live · light") { RoomLiveView(state: RoomsFixtures.live) }
#Preview("Live · dark") { RoomLiveView(state: RoomsFixtures.live).previewDark() }
#Preview("Live · AX3") { RoomLiveView(state: RoomsFixtures.live).previewLargeType() }
