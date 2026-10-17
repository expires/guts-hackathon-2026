// Rebuilt by W9 from Play-Live.dc.html (ADR 0026, 0029). First draft by W7.
import SwiftUI

/// Live Same Life room: your life, the live rival strip, this year's story, the open event or AGE.
struct RoomLiveView: View {
    let state: RoomLiveViewState
    var actions: RoomLiveActions = .noop

    var body: some View {
        VStack(spacing: 0) {
            header
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                RivalStripView(state: state.rivals, caption: state.rivalCaption)
                if let connection = state.connection {
                    RoomConnectionBanner(state: connection, onRetry: actions.onReconnect)
                }
            }
            .padding(.horizontal, Theme.Spacing.m)
            .padding(.vertical, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.Palette.paper)
            .overlay(alignment: .bottom) { Rectangle().fill(Theme.Palette.ink).frame(height: Theme.outline) }

            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                    story
                    if let event = state.event { eventCard(event) }
                    stats
                    controls
                }
                .foregroundStyle(Theme.Palette.ink)
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.top, Theme.Spacing.l)
                .padding(.bottom, Theme.Spacing.xxl)
            }
        }
        .paperBackground()
    }

    private var header: some View {
        HStack(spacing: Theme.Spacing.m) {
            HeaderSquareButton(kind: .back, identifier: "roomLive.leave", action: actions.onLeave)
                .accessibilityLabel("Leave the room")
            LLIconImage(LLIcon(rawValue: state.face) ?? .facePriya, size: 40)
                .frame(width: 48, height: 48)
                .inkSurface(HandCut((18, 22, 17, 21), (21, 17, 22, 18)), fill: Theme.Palette.family)
            VStack(alignment: .leading, spacing: 0) {
                Text(state.name).font(.llBodyBold).lineLimit(1)
                Text(state.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted).lineLimit(1)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            VStack(alignment: .trailing, spacing: 0) {
                LLAmount(state.bank).font(.llTitle).lineLimit(1).minimumScaleFactor(0.7)
                    .contentTransition(.numericText(value: state.bank))
                Text("In the bank").font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
            .accessibilityElement(children: .combine)
        }
        .foregroundStyle(Theme.Palette.ink)
        .padding(.horizontal, Theme.Spacing.margin)
        .padding(.vertical, 14)
        .background(Theme.Palette.surface)
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.Palette.ink).frame(height: Theme.outline) }
    }

    private var story: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text(state.storyTitle).font(.llTitle).accessibilityAddTraits(.isHeader)
                Spacer(minLength: Theme.Spacing.s)
                if state.isSampleData { DemoDataBadge() }
            }
            if let waiting = state.waitingText {
                Text(waiting).font(.llBody).foregroundStyle(Theme.Palette.muted).accessibilityIdentifier("roomLive.waiting")
            }
            ForEach(Array(state.storyLines.enumerated()), id: \.offset) { _, line in
                Text(line).font(.llBody).fixedSize(horizontal: false, vertical: true)
            }
            if !state.lessonTitle.isEmpty {
                Button(action: actions.onOpenLesson) {
                    HStack(spacing: Theme.Spacing.m) {
                        VStack(alignment: .leading, spacing: 0) {
                            Text(state.lessonTitle).font(.llBodyBold)
                            Text("See what happened and rewind").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                        Spacer(minLength: 0)
                        Chevron()
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, Theme.Spacing.m)
                    .frame(minHeight: Theme.minTarget)
                    .inkSurface(.card)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("roomLive.lesson")
            }
        }
    }

    private func eventCard(_ event: RoomLiveViewState.Event) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Text(event.title).font(.llTitle).accessibilityAddTraits(.isHeader)
            Text(event.text).font(.llBody).fixedSize(horizontal: false, vertical: true)
            ForEach(Array(event.choices.enumerated()), id: \.element.id) { offset, choice in
                Button { actions.onChoose(event.id, choice.id) } label: {
                    Text(choice.label).lineLimit(2).minimumScaleFactor(0.8)
                }
                .buttonStyle(SecondButtonStyle(shape: offset.isMultiple(of: 2) ? .buttonAlt : .buttonThird))
                .disabled(state.isBusy)
                .accessibilityIdentifier("roomLive.choice.\(choice.id)")
            }
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.hero, fill: Theme.Palette.surface, hero: true)
        .accessibilityIdentifier("roomLive.event")
    }

    private var stats: some View {
        VStack(spacing: Theme.Spacing.s) {
            ForEach(state.stats) { stat in
                HStack(spacing: 10) {
                    LLIconImage(LLIcon(rawValue: stat.icon) ?? .happiness, size: 24)
                    Text(stat.title).font(.llLabelBold).frame(width: 84, alignment: .leading)
                    InkProgressBar(value: Double(stat.value) / 100, color: stat.id == "money" ? Theme.Palette.money : Theme.Palette.ink)
                    Text("\(stat.value)%").font(.llLabelBold).frame(width: 44, alignment: .trailing)
                        .contentTransition(.numericText(value: Double(stat.value)))
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(stat.title) \(stat.value) out of 100")
            }
        }
    }

    @ViewBuilder
    private var controls: some View {
        if let ageTitle = state.ageTitle {
            Button(action: actions.onAge) {
                HStack(spacing: 10) {
                    LLIconImage(.age, size: 24)
                    Text(ageTitle).lineLimit(1)
                }
            }
            .buttonStyle(.main)
            .disabled(state.isBusy)
            .accessibilityIdentifier("roomLive.age")
        }
        if state.canOpenLife {
            Button("Open in the Life tab", action: actions.onOpenLife)
                .buttonStyle(.text)
                .frame(maxWidth: .infinity)
                .accessibilityIdentifier("roomLive.openLife")
        }
        if state.canFinish {
            Button(action: actions.onFinish) {
                HStack(spacing: 10) {
                    LLIconImage(.trophy, size: 24)
                    Text("Finish my run").lineLimit(1)
                }
            }
            .buttonStyle(.second)
            .disabled(state.isBusy)
            .accessibilityIdentifier("roomLive.finish")
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Age · light") { RoomLiveView(state: RoomFlowFixtures.liveAge) }
#Preview("Age · dark") { RoomLiveView(state: RoomFlowFixtures.liveAge).previewDark() }
#Preview("Age · AX3") { RoomLiveView(state: RoomFlowFixtures.liveAge).previewLargeType() }
#Preview("Event · light") { RoomLiveView(state: RoomFlowFixtures.liveEvent) }
#Preview("Event · dark") { RoomLiveView(state: RoomFlowFixtures.liveEvent).previewDark() }
#Preview("Event · AX3") { RoomLiveView(state: RoomFlowFixtures.liveEvent).previewLargeType() }
#Preview("Starting · light") { RoomLiveView(state: RoomFlowFixtures.liveStarting) }
#Preview("Offline · light") { RoomLiveView(state: RoomFlowFixtures.liveOffline) }
#Preview("Demo live · light") { RoomLiveView(state: RoomsFixtures.live) }
