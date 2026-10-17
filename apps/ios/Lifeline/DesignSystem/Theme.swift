import SwiftUI

/// Spacing, sizes and colours used across the app.
enum Theme {
    enum Spacing {
        static let xs: CGFloat = 4
        static let s: CGFloat = 8
        static let m: CGFloat = 12
        static let l: CGFloat = 16
        static let xl: CGFloat = 24
    }

    /// Minimum touch target (Apple HIG).
    static let minTarget: CGFloat = 44
    static let cornerRadius: CGFloat = 20

    enum StatColor {
        static let happiness = Color.yellow
        static let health = Color.red
        static let smarts = Color.blue
        static let money = Color.green
    }

    static func color(for stat: StatKind) -> Color {
        switch stat {
        case .happiness: StatColor.happiness
        case .health: StatColor.health
        case .smarts: StatColor.smarts
        case .money: StatColor.money
        }
    }

    static func systemImage(for stat: StatKind) -> String {
        switch stat {
        case .happiness: "face.smiling"
        case .health: "heart.fill"
        case .smarts: "brain.head.profile"
        case .money: "sterlingsign.circle"
        }
    }

    static func color(for status: DataStatus) -> Color {
        switch status {
        case .live: .green
        case .cached: .orange
        case .mock: .gray
        }
    }
}

/// Motion rules from BUILD_SPEC section 1. With Reduce Motion on, every animation is a short cross-fade.
enum Motion {
    static let standard = Animation.spring(response: 0.35, dampingFraction: 1.0)
    static let sheet = Animation.spring(response: 0.3, dampingFraction: 0.8)
    static let crossFade = Animation.easeInOut(duration: 0.2)

    static func standard(reduceMotion: Bool) -> Animation {
        reduceMotion ? crossFade : standard
    }

    static func sheet(reduceMotion: Bool) -> Animation {
        reduceMotion ? crossFade : sheet
    }

    static func transition(reduceMotion: Bool) -> AnyTransition {
        reduceMotion ? .opacity : .move(edge: .top).combined(with: .opacity)
    }
}

/// Card surface with Liquid Glass.
struct GlassCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(Theme.Spacing.l)
            .frame(maxWidth: .infinity, alignment: .leading)
            .glassEffect(.regular, in: .rect(cornerRadius: Theme.cornerRadius))
    }
}
