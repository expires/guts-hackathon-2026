// Rebuilt for ADR 0026 by W7. Solo and friends entry by W9 (ADR 0048 compact, ADR 0052).
import SwiftUI

/// Play tab (PENNY_V3_BUILD F4): "Play with friends", "Learn", Join and Circles. The cut Life game,
/// challenges and collection show only with `FeatureFlags.showsCutFeatures`.
struct PlayView: View {
    enum Segment: String, CaseIterable, Identifiable {
        case challenges = "Challenges"
        case collection = "Collection"
        var id: String { rawValue }
    }

    let state: PlayViewState
    var actions: PlayActions = .noop
    /// UI-only selection.
    @State private var segment: Segment = .challenges
    @Environment(\.llPresentationMode) private var presentation

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text("Play").font(.llBodyBold).accessibilityAddTraits(.isHeader)
                if let active = state.rooms?.activeRoom {
                    activeRoom(active)
                }
                PlayChoiceCard(
                    icon: .tabYou, title: L10n.tr("Play as yourself"),
                    detail: L10n.tr("Start from your own money. Connect Monzo or Trading 212, or try a sample student."),
                    fill: Theme.Palette.money, shape: .hero, hero: true, identifier: "play.yourself",
                    action: actions.onPlayAsYourself
                )
                PlayChoiceCard(
                    icon: .family, title: L10n.tr("Play with friends"),
                    detail: L10n.tr("Quick Life, Money Quiz and more. Friends join with a QR code or a short code."),
                    fill: Theme.Palette.family, shape: .hero, hero: true, identifier: "play.friends",
                    action: actions.onPlayWithFriends
                )
                if let learn = state.learn {
                    learnCard(learn)
                }
                Button(action: actions.onJoin) {
                    HStack(spacing: 10) {
                        LLIconImage(.scan, size: 24)
                        Text("Join a game").lineLimit(1)
                    }
                }
                .buttonStyle(.second)
                .accessibilityHint("Opens the camera to scan a room code. You can type the code instead.")
                .accessibilityIdentifier("play.join")
                if let circles = state.circles {
                    BlockTitle(text: L10n.tr("Circles"))
                        .padding(.top, Theme.Spacing.s)
                    CirclesContent(state: circles, actions: actions.circles)
                }
                // PENNY_V3_BUILD F: the full Life game, Challenges and Collection hide behind one flag.
                if state.showsCutFeatures { cutFeatures }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.xs)
            .padding(.bottom, Theme.Spacing.xl)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    /// Cut features (PENNY_V3_BUILD F): Play solo, Challenges and Collection. Shown only with the flag.
    @ViewBuilder
    private var cutFeatures: some View {
        PlayChoiceCard(
            icon: .tabLife, title: L10n.tr("Play solo"),
            detail: L10n.tr("Live a life from 18. Make the money choices. See where they lead."),
            fill: Theme.Palette.money, shape: .cardAlt, identifier: "play.solo",
            action: actions.onPlaySolo
        )
        SegmentBar(segments: Segment.allCases, selected: segment) { segment = $0 }
            .padding(.top, Theme.Spacing.s)
        switch segment {
        case .challenges: phaseContent { challenges }
        case .collection: phaseContent { collection }
        }
    }

    /// "Learn" (ADR 0068): course progress and the next lesson.
    private func learnCard(_ learn: LearnEntryState) -> some View {
        let detail = learn.isLoading
            ? L10n.tr("Short money lessons. Start any lesson.")
            : [learn.progressText, learn.nextText].compactMap { $0 }.joined(separator: "\n")
        return PlayChoiceCard(
            icon: .lesson, title: L10n.tr("Learn"), detail: detail,
            fill: Theme.Palette.work, shape: .card, identifier: "play.learn",
            progress: learn.isLoading ? nil : learn.progress,
            action: actions.onOpenLearn
        )
    }

    private func activeRoom(_ active: RoomEntryViewState.ActiveRoom) -> some View {
        Button(action: actions.rooms.onOpenActiveRoom) {
            HStack(spacing: Theme.Spacing.m) {
                VStack(alignment: .leading, spacing: 0) {
                    Text("Back to room \(active.code)").font(.llBodyBold)
                    Text(active.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Chevron()
            }
            .padding(.horizontal, Theme.Spacing.l)
            .frame(minHeight: Theme.buttonHeight)
            .inkSurface(.badge, fill: Theme.Palette.surface)
            .foregroundStyle(Theme.Palette.ink)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(L10n.tr("Back to room \(active.code). \(active.detail)"))
        .accessibilityIdentifier("play.activeRoom")
    }

    @ViewBuilder
    private func phaseContent(@ViewBuilder _ content: () -> some View) -> some View {
        switch state.phase {
        case .loading:
            SkeletonList(rows: 3)
        case let .failed(error):
            ErrorStateView(state: error, onRetry: actions.onRetry)
        case .ready:
            content()
        }
    }

    private var challenges: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            if let continueText = state.continueText {
                Button(action: actions.onPlay) {
                    Text(continueText).lineLimit(1).minimumScaleFactor(0.7)
                }
                .buttonStyle(.second)
                .accessibilityIdentifier("play.continue")
            }
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
                                    if let status = challenge.status {
                                        Chip(text: status.text, fill: status == .won ? Theme.Palette.money : Theme.Palette.surface)
                                            .padding(.top, 2)
                                    }
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
                        .accessibilityHint(challenge.isYou ? L10n.tr("Shows the Money tab.") : L10n.tr("Starts a life for this challenge."))
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
                tile(icon: .ribbon, value: "\(state.ribbonsTotal)", label: L10n.tr("Ribbons"))
                Button(action: actions.onOpenConcepts) {
                    if let learn = state.learn, !learn.isLoading {
                        tile(icon: .lesson, value: "\(learn.done)/\(learn.total)", label: L10n.tr("Lessons"))
                    } else {
                        tile(icon: .lesson, value: "\(state.conceptsUnlocked)/\(state.conceptsTotal)", label: L10n.tr("Concepts"))
                    }
                }
                .buttonStyle(.plain)
                .accessibilityLabel(state.learn.map { $0.isLoading ? state.conceptsText : $0.progressText } ?? state.conceptsText)
                .accessibilityIdentifier("play.concepts")
            }
            Text(state.ribbonsText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            BlockTitle(text: L10n.tr("Your lives"))
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
                                    LLAmount(life.netWorth, style: .compact).font(.llLabel)
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
                        .accessibilityLabel(L10n.tr("\(life.name), \(life.detail), INDEX \(Int(life.index.rounded())), \(RoomAmount.spoken(life.netWorth, presentation: presentation))"))
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

/// Big Play tab choice: icon on a colour tile, title and one line. Whole card is the button.
struct PlayChoiceCard: View {
    let icon: LLIcon
    let title: String
    let detail: String
    var fill: Color = Theme.Palette.surface
    var shape: HandCut = .card
    var hero = false
    var identifier = ""
    /// 0 to 1: a thin bar under the detail (the Learn card). Nil hides it.
    var progress: Double? = nil
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.l) {
                LLIconImage(icon, size: 40)
                    .frame(width: 64, height: 64)
                    .inkSurface(.badge, fill: fill)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.llTitle).lineLimit(1).minimumScaleFactor(0.8)
                    Text(detail).font(.llLabel).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
                    if let progress {
                        InkProgressBar(value: progress, height: 10)
                            .padding(.top, Theme.Spacing.xs)
                            .accessibilityHidden(true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Chevron()
            }
            .padding(Theme.Spacing.l)
            .frame(minHeight: 96)
            .inkSurface(shape, hero: hero)
            .foregroundStyle(Theme.Palette.ink)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier(identifier)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Rooms · light") { PlayView(state: PlayFixturesW7.withRoom).previewInNavigation() }
#Preview("Rooms · dark") { PlayView(state: PlayFixturesW7.withRoom).previewInNavigation().previewDark() }
#Preview("Rooms · AX3") { PlayView(state: PlayFixturesW7.withRoom).previewInNavigation().previewLargeType() }
#Preview("Rooms entry · light") { PlayView(state: PlayFixturesW7.withEntry).previewInNavigation() }
#Preview("Rooms entry · dark") { PlayView(state: PlayFixturesW7.withEntry).previewInNavigation().previewDark() }
#Preview("Ready · light") { PlayView(state: Fixtures.Play.ready).previewInNavigation() }
#Preview("Ready · dark") { PlayView(state: Fixtures.Play.ready).previewInNavigation().previewDark() }
#Preview("Ready · AX3") { PlayView(state: Fixtures.Play.ready).previewInNavigation().previewLargeType() }
#Preview("No lives · light") { PlayView(state: Fixtures.Play.noLives).previewInNavigation() }
#Preview("Loading · light") { PlayView(state: Fixtures.Play.loading).previewInNavigation() }
#Preview("Error · light") { PlayView(state: Fixtures.Play.error).previewInNavigation() }
