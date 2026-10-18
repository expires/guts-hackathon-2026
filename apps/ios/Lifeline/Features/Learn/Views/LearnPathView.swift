// Draft by W9 (ADR 0068 Learn). Owned by the UI owner from creation.
import SwiftUI

/// The Learn course as a level map: six units, each a winding line of lesson nodes.
struct LearnPathView: View {
    let state: LearnPathViewState
    var actions: LearnPathActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    /// UI-only: the path scrolls to the next lesson once per appearance.
    @State private var didScroll = false

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
                    header
                    content
                }
                .foregroundStyle(Theme.Palette.ink)
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.top, Theme.Spacing.xs)
                .padding(.bottom, 120)
            }
            .paperBackground()
            .onAppear { scrollToNext(proxy) }
            .onChange(of: state.nextLessonID) { _, _ in scrollToNext(proxy) }
            .onChange(of: state.phase) { _, _ in scrollToNext(proxy) }
        }
        .overlay(alignment: .bottom) {
            if let message = state.lockedMessage {
                LearnLockedBanner(message: message, onDismiss: actions.onDismissLocked)
                    .padding(.horizontal, Theme.Spacing.margin)
                    .padding(.bottom, Theme.Spacing.l)
                    .transition(reduceMotion ? .opacity : .move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(reduceMotion ? nil : Motion.sheet, value: state.lockedMessage)
        .toolbar(.hidden, for: .navigationBar)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            HStack(spacing: Theme.Spacing.m) {
                HeaderSquareButton(kind: .back, identifier: "learn.back", action: actions.onClose)
                Text(L10n.tr("Learn"))
                    .font(.llScreenHeader)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityAddTraits(.isHeader)
            }
            if state.phase == .ready {
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Text(state.progressText).font(.llBodyBold)
                    InkProgressBar(value: state.progress)
                    Text(L10n.tr("Every lesson is open. The path shows a good order."))
                        .font(.llLabel)
                        .foregroundStyle(Theme.Palette.muted)
                }
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("learn.progress")
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        switch state.phase {
        case .loading:
            LearnPathSkeleton()
        case let .failed(error):
            ErrorStateView(state: error, onRetry: actions.onRetry)
        case .ready:
            ForEach(Array(state.units.enumerated()), id: \.element.id) { number, unit in
                VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                    LearnUnitHeader(unit: unit, fill: Self.unitFill(number))
                    LearnTrail(nodes: unit.nodes, onSelect: actions.onSelect)
                }
            }
        }
    }

    /// Unit colours cycle through the area palette.
    static func unitFill(_ index: Int) -> Color {
        let fills = [Theme.Palette.money, Theme.Palette.work, Theme.Palette.health, Theme.Palette.home, Theme.Palette.family, Theme.Palette.other]
        return fills[index % fills.count]
    }

    private func scrollToNext(_ proxy: ScrollViewProxy) {
        guard !didScroll, state.phase == .ready, let id = state.nextLessonID else { return }
        didScroll = true
        Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(250))
            if reduceMotion {
                proxy.scrollTo(id, anchor: .center)
            } else {
                withAnimation(Motion.standard) { proxy.scrollTo(id, anchor: .center) }
            }
        }
    }
}

/// Unit card: "Unit 1", title, one line, and "3/8".
struct LearnUnitHeader: View {
    let unit: LearnPathViewState.UnitSection
    let fill: Color

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            VStack(alignment: .leading, spacing: 2) {
                Text(unit.eyebrow).llEyebrow()
                Text(unit.title).font(.llTitle).fixedSize(horizontal: false, vertical: true)
                Text(unit.description).font(.llLabel).fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Text(unit.progressText)
                .font(.llBodyBold)
                .monospacedDigit()
                .padding(.horizontal, Theme.Spacing.s)
                .padding(.vertical, 2)
                .inkSurface(.chip, fill: Theme.Palette.surface, lineWidth: Theme.chipOutline)
                .foregroundStyle(Theme.Palette.ink)
        }
        .foregroundStyle(Theme.Palette.onArea)
        .padding(Theme.Spacing.l)
        .inkSurface(.cardAlt, fill: fill)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel([unit.eyebrow, unit.title, unit.description, unit.progressLabel].joined(separator: ". "))
        .accessibilityAddTraits(.isHeader)
        .accessibilityIdentifier("learn.unit.\(unit.id)")
    }
}

/// Lesson nodes along a winding line. Each row is one lesson; the line joins the node centres.
struct LearnTrail: View {
    let nodes: [LearnPathViewState.Node]
    let onSelect: @MainActor (String) -> Void
    @ScaledMetric(relativeTo: .footnote) private var rowHeight: CGFloat = 132

    static let nodeSize: CGFloat = 72
    static let amplitude: CGFloat = 88

    var body: some View {
        VStack(spacing: 0) {
            ForEach(nodes) { node in
                LearnNodeButton(node: node) { onSelect(node.id) }
                    .offset(x: node.offset * Self.amplitude)
                    .frame(maxWidth: .infinity, minHeight: rowHeight, alignment: .top)
                    .id(node.id)
            }
        }
        .background(alignment: .top) {
            ZStack {
                TrailLine(offsets: nodes.map(\.offset), rowHeight: rowHeight, amplitude: Self.amplitude, top: Self.nodeSize / 2)
                    .stroke(Theme.Palette.rule, style: StrokeStyle(lineWidth: 8, lineCap: .round, lineJoin: .round, dash: [2, 14]))
                TrailLine(offsets: nodes.map(\.offset), rowHeight: rowHeight, amplitude: Self.amplitude, top: Self.nodeSize / 2, upTo: doneCount)
                    .stroke(Theme.Palette.money, style: StrokeStyle(lineWidth: 8, lineCap: .round, lineJoin: .round))
            }
            .accessibilityHidden(true)
        }
    }

    /// The solid line runs through the passed lessons up to the first unpassed one.
    private var doneCount: Int {
        let passed = nodes.prefix { $0.status == .passed }.count
        return passed < nodes.count ? passed : nodes.count - 1
    }
}

/// The line through node centres. `upTo` stops after that many segments (nil: the whole line).
struct TrailLine: Shape {
    let offsets: [Double]
    let rowHeight: CGFloat
    let amplitude: CGFloat
    let top: CGFloat
    var upTo: Int?

    func path(in rect: CGRect) -> Path {
        var path = Path()
        let points = offsets.enumerated().map { index, offset in
            CGPoint(x: rect.midX + offset * amplitude, y: top + CGFloat(index) * rowHeight)
        }
        guard let first = points.first else { return path }
        path.move(to: first)
        let segments = min(upTo ?? points.count - 1, points.count - 1)
        guard segments > 0 else { return path }
        for index in 1...segments {
            let from = points[index - 1]
            let to = points[index]
            let mid = (from.y + to.y) / 2
            path.addCurve(to: to, control1: CGPoint(x: from.x, y: mid), control2: CGPoint(x: to.x, y: mid))
        }
        return path
    }
}

/// One lesson: a round icon button with its title under it.
struct LearnNodeButton: View {
    let node: LearnPathViewState.Node
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 6) {
                LearnNodeCircle(node: node)
                Text(node.title)
                    .font(.llLabelBold)
                    .multilineTextAlignment(.center)
                    .lineLimit(3)
                    .minimumScaleFactor(0.8)
                    .foregroundStyle(node.status == .locked ? Theme.Palette.muted : Theme.Palette.ink)
                    .padding(.horizontal, 6)
                    .background(Theme.Palette.paper, in: .rect(cornerRadius: 6))
                    .frame(width: 150)
            }
            .contentShape(.rect)
        }
        .buttonStyle(LearnNodeStyle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(node.accessibilityLabel)
        .accessibilityHint(node.status == .locked ? L10n.tr("Shows what to finish first") : L10n.tr("Opens the lesson"))
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier("learn.node.\(node.id)")
    }
}

private struct LearnNodeStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .offset(x: configuration.isPressed ? 2 : 0, y: configuration.isPressed ? 2 : 0)
    }
}

/// Passed: green with a check. Open: white with a pulsing ring. Locked: grey with a lock.
struct LearnNodeCircle: View {
    let node: LearnPathViewState.Node
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var pulse = false

    private var fill: Color {
        switch node.status {
        case .passed: Theme.Palette.money
        case .open: Theme.Palette.surface
        case .locked: Theme.Palette.other
        }
    }

    var body: some View {
        ZStack {
            // Only the next lesson pulses: every lesson is open (PENNY_V3_BUILD E1).
            if node.status == .open && node.isNext {
                Circle()
                    .stroke(Theme.Palette.home, lineWidth: 5)
                    .frame(width: LearnTrail.nodeSize + 14, height: LearnTrail.nodeSize + 14)
                    .scaleEffect(reduceMotion ? 1 : (pulse ? 1.12 : 0.96))
                    .opacity(reduceMotion ? 1 : (pulse ? 0.35 : 1))
            }
            Circle()
                .fill(Theme.Palette.ink)
                .offset(x: 3, y: 4)
                .opacity(node.status == .locked ? 0 : 1)
            Circle().fill(fill)
            Circle().strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline)
            Image(systemName: node.symbol)
                .font(.system(size: 28, weight: .semibold))
                .foregroundStyle(node.status == .locked ? Theme.Palette.muted : (node.status == .passed ? Theme.Palette.onArea : Theme.Palette.ink))
                .opacity(node.status == .locked ? 0.7 : 1)
        }
        .frame(width: LearnTrail.nodeSize, height: LearnTrail.nodeSize)
        .overlay(alignment: .bottomTrailing) {
            switch node.status {
            case .passed: badge(LLIconImage(.check, size: 18), fill: Theme.Palette.surface)
            case .locked: badge(LLIconImage(.lock, size: 18), fill: Theme.Palette.surface)
            case .open: EmptyView()
            }
        }
        .overlay(alignment: .topTrailing) {
            if node.hasLifeBonus {
                badge(Image(systemName: "star.fill").font(.system(size: 12, weight: .bold)).foregroundStyle(Theme.Palette.onArea), fill: Theme.Palette.home)
                    .offset(x: 4, y: -4)
            }
        }
        .onAppear {
            guard node.status == .open, node.isNext, !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.2).repeatForever(autoreverses: true)) { pulse = true }
        }
        .onChange(of: reduceMotion) { _, reduce in if reduce { pulse = false } }
    }

    private func badge(_ content: some View, fill: Color) -> some View {
        content
            .frame(width: 26, height: 26)
            .background(Circle().fill(fill))
            .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: Theme.chipOutline))
    }
}

/// "Finish Needs and wants first" after a tap on a locked lesson.
struct LearnLockedBanner: View {
    let message: String
    let onDismiss: () -> Void

    var body: some View {
        HStack(spacing: Theme.Spacing.m) {
            LLIconImage(.lock, size: 24)
            Text(message)
                .font(.llBodyBold)
                .frame(maxWidth: .infinity, alignment: .leading)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("learn.locked.message")
            Button(action: onDismiss) {
                Image(systemName: "xmark")
                    .font(.system(size: 14, weight: .bold))
                    .frame(width: Theme.minTarget, height: Theme.minTarget)
                    .contentShape(.rect)
            }
            .buttonStyle(.plain)
            .accessibilityLabel(L10n.tr("Close"))
        }
        .foregroundStyle(Theme.Palette.ink)
        .padding(.leading, Theme.Spacing.l)
        .padding(.vertical, Theme.Spacing.xs)
        .inkSurface(.badge, fill: Theme.Palette.surface, hero: true)
        .onAppear { AccessibilityNotification.Announcement(message).post() }
        .accessibilityIdentifier("learn.locked")
    }
}

/// Loading shape of the path: a unit card and a few nodes.
struct LearnPathSkeleton: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.xl) {
            LLSkeleton(.block(height: 96))
            ForEach(0..<4, id: \.self) { index in
                LLSkeleton(.circle(diameter: LearnTrail.nodeSize))
                    .offset(x: LearnMapping.wave[index] * LearnTrail.amplitude)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(L10n.tr("Loading your lessons"))
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Path · light") { LearnPathView(state: LearnFixtures.path) }
#Preview("Path · dark") { LearnPathView(state: LearnFixtures.path).previewDark() }
#Preview("Path · AX3") { LearnPathView(state: LearnFixtures.path).previewLargeType() }
#Preview("Locked tap · light") { LearnPathView(state: LearnFixtures.pathLocked) }
#Preview("Locked tap · dark") { LearnPathView(state: LearnFixtures.pathLocked).previewDark() }
#Preview("Locked tap · AX3") { LearnPathView(state: LearnFixtures.pathLocked).previewLargeType() }
#Preview("Loading · light") { LearnPathView(state: LearnFixtures.pathLoading) }
#Preview("Error · light") { LearnPathView(state: LearnFixtures.pathError) }
