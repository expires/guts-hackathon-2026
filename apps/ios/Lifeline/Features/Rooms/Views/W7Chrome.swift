import SwiftUI

// View helpers shared by W7 screens (Test it, Lesson, Rewind, Summary, Rooms, You, Store).
// They only combine DesignSystem tokens and components (ADR 0026). No data, no logic.

/// Small outlined label chip (13 bold), for "Lesson", "Game result", "2 rewinds left".
struct OutlineTag: View {
    let text: String
    var icon: LLIcon?
    var fill: Color = Theme.Palette.surface
    var eyebrow = false

    var body: some View {
        HStack(spacing: 6) {
            if let icon { LLIconImage(icon, size: 24) }
            if eyebrow {
                Text(text).llEyebrow()
            } else {
                Text(text).font(.llLabelBold)
            }
        }
        .foregroundStyle(fill == Theme.Palette.surface ? Theme.Palette.ink : Theme.Palette.onArea)
        .padding(.horizontal, 10)
        .padding(.vertical, 3)
        .inkSurface(.badge, fill: fill, lineWidth: Theme.chipOutline)
    }
}

/// Medal with two tails, filled with an area colour (Life summary ribbons).
struct RibbonMedal: View {
    var color: Color
    var size: CGFloat = 48

    var body: some View {
        Canvas { context, canvas in
            let s = canvas.width / 48
            var tails = Path()
            for points in [[(16, 34), (10, 54), (18, 49), (22, 55), (24, 36)], [(32, 34), (38, 54), (30, 49), (26, 55), (24, 36)]] {
                tails.move(to: CGPoint(x: CGFloat(points[0].0) * s, y: CGFloat(points[0].1) * s))
                for point in points.dropFirst() { tails.addLine(to: CGPoint(x: CGFloat(point.0) * s, y: CGFloat(point.1) * s)) }
            }
            let ink = Theme.Palette.ink
            context.fill(tails, with: .color(color))
            context.stroke(tails, with: .color(ink), style: StrokeStyle(lineWidth: 2.5 * s, lineJoin: .round))
            let outer = Path(ellipseIn: CGRect(x: 5 * s, y: 3 * s, width: 38 * s, height: 38 * s))
            context.fill(outer, with: .color(color))
            context.stroke(outer, with: .color(ink), lineWidth: 3 * s)
            let inner = Path(ellipseIn: CGRect(x: 14 * s, y: 12 * s, width: 20 * s, height: 20 * s))
            context.fill(inner, with: .color(Theme.Palette.surface))
            context.stroke(inner, with: .color(ink), lineWidth: 2.5 * s)
        }
        .frame(width: size, height: size * 56 / 48)
        .accessibilityHidden(true)
    }
}

/// Section label, 17 bold.
struct BlockTitle: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.llBodyBold)
            .foregroundStyle(Theme.Palette.ink)
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityAddTraits(.isHeader)
    }
}

extension Area {
    /// Cycles through the 5 colour areas, so neighbours differ (ribbons, rivals).
    static func cycling(_ index: Int) -> Area {
        let order: [Area] = [.home, .money, .work, .family, .health]
        return order[((index % order.count) + order.count) % order.count]
    }
}
