// Rebuilt for ADR 0026 (Play-Lobby.dc.html) by W7.
import SwiftUI

/// Play tab: Same Life rooms, challenges, and your collection (lives, ribbons, concepts).
struct PlayView: View {
    enum Segment: String, CaseIterable, Identifiable {
        case rooms = "Rooms"
        case challenges = "Challenges"
        case collection = "Collection"
        var id: String { rawValue }
    }

    let state: PlayViewState
    var actions: PlayActions = .noop
    /// UI-only selection. The Rooms segment opens first when a room exists.
    @State private var segment: Segment?

    private var selected: Segment { segment ?? (state.room == nil ? .challenges : .rooms) }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                HStack {
                    Text("Play").font(.llTitle).accessibilityAddTraits(.isHeader)
                    Spacer()
                    if state.isSampleData || state.room?.isSampleData == true { DemoDataBadge() }
                }
                SegmentBar(segments: Segment.allCases.filter { $0 != .rooms || state.room != nil }, selected: selected) { segment = $0 }
                switch selected {
                case .rooms:
                    if let room = state.room {
                        RoomLobbyContent(state: room, actions: actions.room)
                            .accessibilityIdentifier("play.rooms")
                    }
                case .challenges:
                    phaseContent { challenges }
                case .collection:
                    phaseContent { collection }
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    @ViewBuilder
    private func phaseContent(@ViewBuilder _ content: () -> some View) -> some View {
        switch state.phase {
        case let .loading(loading):
            LoadingStateView(state: loading)
        case let .failed(error):
            ErrorStateView(state: error, onRetry: actions.onRetry)
        case .ready:
            content()
        }
    }

    private var challenges: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Button(action: actions.onPlay) {
                Text(state.continueText ?? "Start a new life").lineLimit(1).minimumScaleFactor(0.7)
            }
            .buttonStyle(.main)
            .lineLimit(1)
            .minimumScaleFactor(0.7)
            .accessibilityIdentifier("play.start")
            if state.challenges.isEmpty {
                Text("No challenges right now.").font(.llBody).foregroundStyle(Theme.Palette.muted)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(state.challenges.enumerated()), id: \.element.id) { offset, challenge in
                        if offset > 0 { RuleDivider() }
                        Button { actions.onStartChallenge(challenge.id) } label: {
                            HStack(alignment: .top, spacing: Theme.Spacing.m) {
                                LLIconImage(LLIcon.from(emoji: challenge.emoji), size: 32)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(challenge.title).font(.llBodyBold)
                                    Text(challenge.description).font(.llBody).fixedSize(horizontal: false, vertical: true)
                                    Text(challenge.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                Chevron()
                            }
                            .foregroundStyle(Theme.Palette.ink)
                            .padding(.horizontal, Theme.Spacing.l)
                            .padding(.vertical, Theme.Spacing.m)
                            .frame(minHeight: Theme.minTarget)
                            .contentShape(.rect)
                        }
                        .buttonStyle(.plain)
                        .disabled(state.isBusy)
                        .accessibilityIdentifier("play.challenge.\(challenge.id)")
                    }
                }
                .inkSurface(.card)
            }
        }
    }

    private var collection: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            HStack(spacing: Theme.Spacing.m) {
                tile(icon: .ribbon, value: "\(state.ribbonsTotal)", label: "Ribbons")
                Button(action: actions.onOpenConcepts) {
                    tile(icon: .lesson, value: "\(state.conceptsUnlocked)/\(state.conceptsTotal)", label: "Concepts")
                }
                .buttonStyle(.plain)
                .accessibilityLabel(state.conceptsText)
                .accessibilityIdentifier("play.concepts")
            }
            Text(state.ribbonsText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            BlockTitle(text: "Your lives")
            if state.lives.isEmpty {
                Text("No lives yet. Start one in Challenges.").font(.llBody).foregroundStyle(Theme.Palette.muted)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(state.lives.enumerated()), id: \.element.id) { offset, life in
                        if offset > 0 { RuleDivider() }
                        Button { actions.onOpenLife(life.id) } label: {
                            HStack(spacing: Theme.Spacing.m) {
                                LLIconImage(LLIcon.face(emoji: life.emoji), size: 32)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(life.name + (life.isCurrent ? " · playing" : "")).font(.llBodyBold)
                                    Text(life.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                VStack(alignment: .trailing, spacing: 0) {
                                    Text("\(Int(life.index.rounded()))").font(.llBodyBold)
                                    Text(Money.compact(life.netWorth)).font(.llLabel)
                                }
                                Chevron()
                            }
                            .foregroundStyle(Theme.Palette.ink)
                            .padding(.horizontal, Theme.Spacing.l)
                            .padding(.vertical, Theme.Spacing.m)
                            .frame(minHeight: Theme.minTarget)
                            .contentShape(.rect)
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("\(life.name), \(life.detail), INDEX \(Int(life.index.rounded())), \(Money.spoken(life.netWorth))")
                        .accessibilityIdentifier("play.life.\(life.id)")
                    }
                }
                .inkSurface(.cardAlt)
            }
        }
    }

    private func tile(icon: LLIcon, value: String, label: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            LLIconImage(icon, size: 24)
            Text(value).font(.llTitle).lineLimit(1).minimumScaleFactor(0.7)
            Text(label).font(.llLabel).foregroundStyle(Theme.Palette.muted)
        }
        .padding(Theme.Spacing.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.card)
        .foregroundStyle(Theme.Palette.ink)
    }
}

/// Hand-cut segmented control: ink fill on the selected segment. View-local until DesignSystem has one.
struct SegmentBar<Segment: Identifiable & RawRepresentable & Hashable>: View where Segment.RawValue == String {
    let segments: [Segment]
    let selected: Segment
    let onSelect: (Segment) -> Void

    private let shapes = [HandCut((12, 16, 11, 15), (15, 11, 16, 12)), HandCut((16, 11, 15, 12), (11, 15, 12, 16)), HandCut((11, 15, 12, 16), (16, 12, 15, 11))]

    var body: some View {
        HStack(spacing: Theme.Spacing.s) {
            ForEach(Array(segments.enumerated()), id: \.element.id) { offset, segment in
                let isOn = segment == selected
                Button { onSelect(segment) } label: {
                    Text(segment.rawValue)
                        .font(.llLabelBold)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .foregroundStyle(isOn ? Theme.Palette.surface : Theme.Palette.ink)
                        .padding(.horizontal, Theme.Spacing.m)
                        .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                        .inkSurface(shapes[offset % shapes.count], fill: isOn ? Theme.Palette.ink : Theme.Palette.surface, lineWidth: Theme.chipOutline)
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(isOn ? [.isSelected, .isButton] : .isButton)
                .accessibilityIdentifier("segment.\(segment.rawValue.lowercased())")
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Rooms · light") { PlayView(state: PlayFixturesW7.withRoom).previewInNavigation() }
#Preview("Rooms · dark") { PlayView(state: PlayFixturesW7.withRoom).previewInNavigation().previewDark() }
#Preview("Rooms · AX3") { PlayView(state: PlayFixturesW7.withRoom).previewInNavigation().previewLargeType() }
#Preview("Ready · light") { PlayView(state: Fixtures.Play.ready).previewInNavigation() }
#Preview("Ready · dark") { PlayView(state: Fixtures.Play.ready).previewInNavigation().previewDark() }
#Preview("Ready · AX3") { PlayView(state: Fixtures.Play.ready).previewInNavigation().previewLargeType() }
#Preview("No lives · light") { PlayView(state: Fixtures.Play.noLives).previewInNavigation() }
#Preview("Loading · light") { PlayView(state: Fixtures.Play.loading).previewInNavigation() }
#Preview("Error · light") { PlayView(state: Fixtures.Play.error).previewInNavigation() }
