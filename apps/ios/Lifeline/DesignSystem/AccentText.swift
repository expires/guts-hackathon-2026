import SwiftUI

extension Theme.Palette {
    /// Light value of `accentText`. 6.2:1 on paper #F5F2EA, 7.0:1 on surface #FFFFFF.
    static let accentTextLight: UInt32 = 0x3451B8
    /// Dark value of `accentText`. 9.5:1 on paper #121318, 8.3:1 on surface #1E2029.
    static let accentTextDark: UInt32 = 0x9DB8FF

    /// Accent text for small links ("2 Replies", "See sources"). At least 4.5:1 on paper and surface
    /// in light and dark (WCAG AA for 13 pt bold). Check with `Theme.contrastRatio`.
    static let accentText = Color(uiColor: UIColor { traits in
        UIColor(hex: traits.userInterfaceStyle == .dark ? accentTextDark : accentTextLight)
    })
}

extension Theme {
    /// WCAG 2 contrast ratio between two sRGB colours given as 0xRRGGBB (1...21).
    static func contrastRatio(_ first: UInt32, _ second: UInt32) -> Double {
        func luminance(_ hex: UInt32) -> Double {
            func channel(_ shift: UInt32) -> Double {
                let value = Double((hex >> shift) & 0xFF) / 255
                return value <= 0.04045 ? value / 12.92 : pow((value + 0.055) / 1.055, 2.4)
            }
            return 0.2126 * channel(16) + 0.7152 * channel(8) + 0.0722 * channel(0)
        }
        let a = luminance(first)
        let b = luminance(second)
        return (max(a, b) + 0.05) / (min(a, b) + 0.05)
    }
}
