import SwiftUI
import UIKit

/// Design tokens from `lifeline-design/HANDOFF.md` (ADR 0026). Theme "Paper", card "White".
///
/// Dark palette (derived from the handoff's "Night" theme, contrast kept):
/// | Token   | Light   | Dark    | Note |
/// |---------|---------|---------|------|
/// | paper   | #F5F2EA | #121318 | screen background |
/// | surface | #FFFFFF | #1E2029 | cards, sheets, tab bar |
/// | ink     | #16181D | #F2F1EC | text, outlines, shadows, main button (ink on paper 15.9:1 light, 15.6:1 dark) |
/// | muted   | #4A4F59 | #A9ABB8 | second-level text (7.9:1 light, 7.6:1 dark) |
/// | rule    | #DDD8CC | #33364A | dividers inside lists |
/// | work    | #6C8EF5 | #7FA6FF | areas: brighter in dark so fills stay visible |
/// | home    | #FFA94D | #FFAE5C | |
/// | money   | #3FB57A | #4FD69C | |
/// | family  | #A78BFA | #BBA2FF | |
/// | health  | #FF7A8A | #FF8FA3 | also "price up" flags |
/// | other   | #CFCAC0 | #4A4D5E | spending "Other" |
/// Text on an area colour is always `onArea` (#16181D) in both modes, so it keeps contrast.
enum Theme {
    enum Palette {
        static let paper = dynamic(light: 0xF5F2EA, dark: 0x121318)
        static let surface = dynamic(light: 0xFFFFFF, dark: 0x1E2029)
        static let ink = dynamic(light: 0x16181D, dark: 0xF2F1EC)
        static let muted = dynamic(light: 0x4A4F59, dark: 0xA9ABB8)
        static let rule = dynamic(light: 0xDDD8CC, dark: 0x33364A)
        static let work = dynamic(light: 0x6C8EF5, dark: 0x7FA6FF)
        static let home = dynamic(light: 0xFFA94D, dark: 0xFFAE5C)
        static let money = dynamic(light: 0x3FB57A, dark: 0x4FD69C)
        static let family = dynamic(light: 0xA78BFA, dark: 0xBBA2FF)
        static let health = dynamic(light: 0xFF7A8A, dark: 0xFF8FA3)
        static let other = dynamic(light: 0xCFCAC0, dark: 0x4A4D5E)
        /// Text and outlines on an area colour. Same in light and dark.
        static let onArea = Color(hex: 0x16181D)
    }

    /// Spacing scale: 4 / 8 / 12 / 16 / 20 / 32.
    enum Spacing {
        static let xs: CGFloat = 4
        static let s: CGFloat = 8
        static let m: CGFloat = 12
        static let l: CGFloat = 16
        static let xl: CGFloat = 20
        static let xxl: CGFloat = 32
        /// Screen side margin.
        static let margin: CGFloat = 20
    }

    /// Minimum touch target.
    static let minTarget: CGFloat = 44
    /// Main buttons are 52 pt tall.
    static let buttonHeight: CGFloat = 52
    /// Outline on cards, buttons and bars.
    static let outline: CGFloat = 3
    /// Outline on chips.
    static let chipOutline: CGFloat = 2
    /// Offset shadow on the hero element of a screen only.
    static let heroShadow = CGSize(width: 6, height: 7)
    /// Kept for older call sites. Cards use `HandCut` shapes.
    static let cornerRadius: CGFloat = 22

    enum StatColor {
        static let happiness = Palette.home
        static let health = Palette.health
        static let smarts = Palette.work
        static let money = Palette.money
    }

    static func color(for stat: StatKind) -> Color {
        switch stat {
        case .happiness: StatColor.happiness
        case .health: StatColor.health
        case .smarts: StatColor.smarts
        case .money: StatColor.money
        }
    }

    static func icon(for stat: StatKind) -> LLIcon {
        switch stat {
        case .happiness: .happiness
        case .health: .health
        case .smarts: .study
        case .money: .savings
        }
    }

    static func color(for status: DataStatus) -> Color {
        switch status {
        case .live: Palette.money
        case .cached: Palette.home
        case .mock, .unavailable: Palette.other
        }
    }

    static func icon(for status: DataStatus) -> LLIcon {
        switch status {
        case .live: .statusLive
        case .cached: .statusCached
        case .mock, .unavailable: .statusMock
        }
    }

    private static func dynamic(light: UInt32, dark: UInt32) -> Color {
        Color(uiColor: UIColor { traits in
            UIColor(hex: traits.userInterfaceStyle == .dark ? dark : light)
        })
    }
}

/// Life areas. Colour is always paired with a word or an icon.
enum Area: String, CaseIterable, Sendable {
    case work, home, money, family, health, other

    var color: Color {
        switch self {
        case .work: Theme.Palette.work
        case .home: Theme.Palette.home
        case .money: Theme.Palette.money
        case .family: Theme.Palette.family
        case .health: Theme.Palette.health
        case .other: Theme.Palette.other
        }
    }

    var label: String { rawValue.capitalized }
}

extension Color {
    init(hex: UInt32) {
        self.init(uiColor: UIColor(hex: hex))
    }
}

extension UIColor {
    convenience init(hex: UInt32) {
        self.init(
            red: CGFloat((hex >> 16) & 0xFF) / 255,
            green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255,
            alpha: 1
        )
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
