import SwiftUI

/// Penny's reaction on an answer (ADR 0031). Matches the contract `reaction` enum.
enum ReactionKind: String, CaseIterable, Sendable {
    /// Data lookup.
    case eyes
    /// Engine, replay or projection.
    case brain
    /// Confirmed action.
    case thumbs
    /// Action done.
    case tick
    /// Low confidence.
    case question
    /// Out of scope.
    case shrug

    /// Asset in `Assets.xcassets/Icons` (`reaction-eyes`, ...), ink line style with a dark variant.
    var assetName: String { "reaction-" + rawValue }

    var accessibilityLabel: String {
        switch self {
        case .eyes: "Penny is looking at your data"
        case .brain: "Penny is working it out"
        case .thumbs: "Penny agrees"
        case .tick: "Done"
        case .question: "Penny is not sure"
        case .shrug: "Penny cannot help with that"
        }
    }
}

/// Round reaction badge with a thought-bubble tail (two small circles towards the bubble's bottom-left).
/// Place it at the top-trailing corner of Penny's first bubble.
struct ReactionBadge: View {
    let reaction: ReactionKind
    var size: CGFloat = 32

    init(_ reaction: ReactionKind, size: CGFloat = 32) {
        self.reaction = reaction
        self.size = size
    }

    /// From the contract value ("eyes", "brain", ...). Unknown values show `question`.
    init(rawValue: String, size: CGFloat = 32) {
        self.init(ReactionKind(rawValue: rawValue) ?? .question, size: size)
    }

    var body: some View {
        ZStack(alignment: .bottomLeading) {
            // Thought-bubble tail.
            dot(size * 0.22)
                .offset(x: -size * 0.12, y: size * 0.12)
            dot(size * 0.13)
                .offset(x: -size * 0.32, y: size * 0.3)
            Image(reaction.assetName)
                .resizable()
                .scaledToFit()
                .padding(size * 0.18)
                .frame(width: size, height: size)
                .background(Circle().fill(Theme.Palette.surface))
                .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: Theme.chipOutline))
        }
        .frame(width: size, height: size)
        .accessibilityElement()
        .accessibilityLabel(reaction.accessibilityLabel)
    }

    private func dot(_ diameter: CGFloat) -> some View {
        Circle()
            .fill(Theme.Palette.surface)
            .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: 1.5))
            .frame(width: diameter, height: diameter)
    }
}

#Preview("Reactions") {
    HStack(spacing: Theme.Spacing.l) {
        ForEach(ReactionKind.allCases, id: \.self) { ReactionBadge($0) }
    }
    .padding(Theme.Spacing.xxl)
    .background(Theme.Palette.paper)
}
