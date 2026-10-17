import SwiftUI

// Skeleton shapes (ADR 0060): while something must load, a screen shows the shape of its real layout,
// never a spinner with text. The shimmer is slow and calm; with Reduce Motion it is off (flat shapes).

/// One placeholder shape.
struct LLSkeleton: View {
    enum Kind: Sendable, Equatable {
        /// A text line. `width` is a fraction of the available width (0...1).
        case line(width: CGFloat = 1, height: CGFloat = 14)
        /// A solid block (chart, image, tile) of a fixed height.
        case block(height: CGFloat)
        /// A round avatar or icon.
        case circle(diameter: CGFloat)
    }

    var kind: Kind

    init(_ kind: Kind) {
        self.kind = kind
    }

    var body: some View {
        switch kind {
        case let .line(width, height):
            GeometryReader { proxy in
                Capsule()
                    .fill(Theme.Palette.rule)
                    .frame(width: proxy.size.width * min(max(width, 0), 1), height: height)
            }
            .frame(height: height)
            .llShimmer()
        case let .block(height):
            HandCut.card.fill(Theme.Palette.rule)
                .frame(maxWidth: .infinity)
                .frame(height: height)
                .llShimmer()
        case let .circle(diameter):
            Circle().fill(Theme.Palette.rule)
                .frame(width: diameter, height: diameter)
                .llShimmer()
        }
    }
}

/// A list row: icon, two lines, trailing value. Same height as `ActionList` rows.
struct SkeletonRow: View {
    var body: some View {
        HStack(spacing: Theme.Spacing.m) {
            LLSkeleton(.circle(diameter: 32))
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                LLSkeleton(.line(width: 0.7))
                LLSkeleton(.line(width: 0.4, height: 11))
            }
            LLSkeleton(.line(width: 1, height: 14))
                .frame(width: 56)
        }
        .frame(minHeight: Theme.minTarget)
        .padding(.vertical, Theme.Spacing.xs)
    }
}

/// A card: title line, a big number line, two body lines, on the card surface.
struct SkeletonCard: View {
    var lines = 2

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            LLSkeleton(.line(width: 0.35, height: 12))
            LLSkeleton(.line(width: 0.55, height: 28))
            ForEach(0..<max(lines, 0), id: \.self) { index in
                LLSkeleton(.line(width: index.isMultiple(of: 2) ? 0.9 : 0.65))
            }
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.card, lineWidth: Theme.chipOutline)
    }
}

/// A stack of rows, optionally under a card. For list screens and the shared `LoadingStateView`.
struct SkeletonList: View {
    var rows = 4
    var showsCard = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            if showsCard { SkeletonCard() }
            ForEach(0..<max(rows, 0), id: \.self) { _ in SkeletonRow() }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Loading")
    }
}

private struct ShimmerModifier: ViewModifier {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var phase: CGFloat = -1

    func body(content: Content) -> some View {
        if reduceMotion {
            content
        } else {
            content
                .overlay {
                    GeometryReader { proxy in
                        LinearGradient(
                            colors: [.clear, Theme.Palette.surface.opacity(0.55), .clear],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                        .frame(width: proxy.size.width * 0.6)
                        .offset(x: phase * proxy.size.width * 1.6)
                    }
                    .mask(content)
                    .allowsHitTesting(false)
                }
                .onAppear {
                    withAnimation(.easeInOut(duration: 1.6).repeatForever(autoreverses: false)) { phase = 1 }
                }
        }
    }
}

extension View {
    /// Calm shimmer for skeleton shapes. Off with Reduce Motion.
    func llShimmer() -> some View {
        modifier(ShimmerModifier())
    }
}

#Preview("Skeletons") {
    ScrollView {
        SkeletonList(rows: 4, showsCard: true)
            .padding(Theme.Spacing.margin)
    }
    .background(Theme.Palette.paper)
}
