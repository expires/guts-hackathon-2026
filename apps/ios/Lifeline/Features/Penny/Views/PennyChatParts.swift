import SwiftUI

// View-local pieces for Ask Penny (W7). Bubbles, reactions, typing dots and the tool-step line come
// from DesignSystem (ChatBubbleShape, ReactionBadge, TypingDots, ToolStepLine).

/// Small outlined button for links and chips. 44 pt target.
struct PennySmallButton: View {
    let title: String
    var identifier = ""
    var filled = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.llLabelBold)
                .lineLimit(1)
                .foregroundStyle(filled ? Theme.Palette.surface : Theme.Palette.ink)
                .padding(.horizontal, Theme.Spacing.m)
                .frame(minHeight: 36)
                .inkSurface(.badge, fill: filled ? Theme.Palette.ink : Theme.Palette.surface, lineWidth: Theme.chipOutline)
                .frame(minHeight: Theme.minTarget)
                .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(identifier)
    }
}

/// Penny's face with motion (DIRECTION_V2 section 6, fix 4).
/// - Idle: a slow 2 pt bob every 3 s and a short blink about every 5 s.
/// - Thinking: a quicker bounce.
/// - Reduce Motion: still.
struct PennyAnimatedFace: View {
    var mood: PennyView.Mood
    var thinking = false
    var size: CGFloat = 36
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: reduceMotion)) { context in
            let t = context.date.timeIntervalSinceReferenceDate
            let motion = reduceMotion ? FaceMotion.still : (thinking ? Self.thinking(at: t) : Self.idle(at: t))
            PennyView(mood: thinking ? .thinking : mood, size: size)
                .scaleEffect(x: 1, y: motion.squash, anchor: .center)
                .offset(y: motion.offset)
        }
        .frame(width: size, height: size)
    }

    struct FaceMotion: Equatable {
        var offset: CGFloat
        var squash: CGFloat
        static let still = FaceMotion(offset: 0, squash: 1)
    }

    /// Idle: up 2 pt and back over the first 0.8 s of each 3 s cycle. A 0.12 s blink (vertical squash)
    /// in the last part of every 5.3 s cycle.
    static func idle(at t: TimeInterval) -> FaceMotion {
        let bobPhase = t.truncatingRemainder(dividingBy: 3)
        let offset: CGFloat = bobPhase < 0.8 ? -2 * CGFloat(sin(.pi * bobPhase / 0.8)) : 0
        let blinkPhase = t.truncatingRemainder(dividingBy: 5.3)
        let squash: CGFloat = blinkPhase > 5.18 ? 0.88 : 1
        return FaceMotion(offset: offset, squash: squash)
    }

    /// Thinking: a 3 pt bounce 2 times a second.
    static func thinking(at t: TimeInterval) -> FaceMotion {
        FaceMotion(offset: -3 * CGFloat(abs(sin(2 * .pi * t))), squash: 1)
    }
}
