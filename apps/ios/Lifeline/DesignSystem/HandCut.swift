import SwiftUI

/// Rounded rectangle with 4 different elliptical corners, like CSS
/// `border-radius: tl tr br bl / tl tr br bl`. The uneven corners give the hand-cut look.
struct HandCut: InsettableShape {
    /// Horizontal radii: top-left, top-right, bottom-right, bottom-left.
    var h: (CGFloat, CGFloat, CGFloat, CGFloat)
    /// Vertical radii, same order.
    var v: (CGFloat, CGFloat, CGFloat, CGFloat)
    var inset: CGFloat = 0

    init(_ h: (CGFloat, CGFloat, CGFloat, CGFloat), _ v: (CGFloat, CGFloat, CGFloat, CGFloat)? = nil) {
        self.h = h
        self.v = v ?? h
    }

    func inset(by amount: CGFloat) -> HandCut {
        var copy = self
        copy.inset += amount
        return copy
    }

    func path(in rect: CGRect) -> Path {
        let r = rect.insetBy(dx: inset, dy: inset)
        func clampX(_ x: CGFloat) -> CGFloat { min(max(0, x - inset), r.width / 2) }
        func clampY(_ y: CGFloat) -> CGFloat { min(max(0, y - inset), r.height / 2) }
        let tl = CGSize(width: clampX(h.0), height: clampY(v.0))
        let tr = CGSize(width: clampX(h.1), height: clampY(v.1))
        let br = CGSize(width: clampX(h.2), height: clampY(v.2))
        let bl = CGSize(width: clampX(h.3), height: clampY(v.3))
        let k: CGFloat = 0.5523 // cubic approximation of a quarter ellipse
        var p = Path()
        p.move(to: CGPoint(x: r.minX + tl.width, y: r.minY))
        p.addLine(to: CGPoint(x: r.maxX - tr.width, y: r.minY))
        p.addCurve(
            to: CGPoint(x: r.maxX, y: r.minY + tr.height),
            control1: CGPoint(x: r.maxX - tr.width + tr.width * k, y: r.minY),
            control2: CGPoint(x: r.maxX, y: r.minY + tr.height - tr.height * k)
        )
        p.addLine(to: CGPoint(x: r.maxX, y: r.maxY - br.height))
        p.addCurve(
            to: CGPoint(x: r.maxX - br.width, y: r.maxY),
            control1: CGPoint(x: r.maxX, y: r.maxY - br.height + br.height * k),
            control2: CGPoint(x: r.maxX - br.width + br.width * k, y: r.maxY)
        )
        p.addLine(to: CGPoint(x: r.minX + bl.width, y: r.maxY))
        p.addCurve(
            to: CGPoint(x: r.minX, y: r.maxY - bl.height),
            control1: CGPoint(x: r.minX + bl.width - bl.width * k, y: r.maxY),
            control2: CGPoint(x: r.minX, y: r.maxY - bl.height + bl.height * k)
        )
        p.addLine(to: CGPoint(x: r.minX, y: r.minY + tl.height))
        p.addCurve(
            to: CGPoint(x: r.minX + tl.width, y: r.minY),
            control1: CGPoint(x: r.minX, y: r.minY + tl.height - tl.height * k),
            control2: CGPoint(x: r.minX + tl.width - tl.width * k, y: r.minY)
        )
        p.closeSubpath()
        return p
    }
}

extension HandCut {
    /// Hero card (Next Move): `22 30 20 28 / 28 20 30 22`.
    static let hero = HandCut((22, 30, 20, 28), (28, 20, 30, 22))
    /// Standard card: `16 20 15 19 / 19 15 20 16`.
    static let card = HandCut((16, 20, 15, 19), (19, 15, 20, 16))
    /// Second card variant, so neighbours differ: `20 15 19 16 / 15 20 16 19`.
    static let cardAlt = HandCut((20, 15, 19, 16), (15, 20, 16, 19))
    /// Main button: `14 20 12 18 / 18 12 20 14`.
    static let button = HandCut((14, 20, 12, 18), (18, 12, 20, 14))
    /// Second button: `18 12 20 14 / 14 20 12 18`.
    static let buttonAlt = HandCut((18, 12, 20, 14), (14, 20, 12, 18))
    /// Third button: `12 18 14 20 / 20 14 18 12`.
    static let buttonThird = HandCut((12, 18, 14, 20), (20, 14, 18, 12))
    /// Mock data chip: `12 16 11 15 / 15 11 16 12`.
    static let badge = HandCut((12, 16, 11, 15), (15, 11, 16, 12))
    /// Small chip ("Up £3"): `8 11 7 10`.
    static let chip = HandCut((8, 11, 7, 10))
    /// Bars (spending, stats): `10 14 9 13 / 13 9 14 10`.
    static let bar = HandCut((10, 14, 9, 13), (13, 9, 14, 10))
    /// Sheet top corners.
    static let sheet = HandCut((28, 34, 0, 0), (30, 26, 0, 0))
    /// Almost-circle for the Age button (percent-based in the design; here in points for 104 pt).
    static let blob = HandCut((52, 50, 54, 51), (51, 54, 50, 53))
}

extension View {
    /// Fill, 3 pt ink outline and optional hero shadow on a hand-cut shape.
    func inkSurface(
        _ shape: HandCut = .card,
        fill: Color = Theme.Palette.surface,
        lineWidth: CGFloat = Theme.outline,
        hero: Bool = false
    ) -> some View {
        background {
            ZStack {
                if hero {
                    shape.fill(Theme.Palette.ink)
                        .offset(x: Theme.heroShadow.width, y: Theme.heroShadow.height)
                }
                shape.fill(fill)
                shape.strokeBorder(Theme.Palette.ink, lineWidth: lineWidth)
            }
        }
        .contentShape(shape)
    }
}
