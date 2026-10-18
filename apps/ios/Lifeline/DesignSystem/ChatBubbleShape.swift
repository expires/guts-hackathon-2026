import SwiftUI

/// Hand-cut chat bubble with a small tail at the bottom corner (ADR 0031, ADR 0026 hand-cut look).
/// `.left` is Penny (tail bottom-left). `.right` is the user (tail bottom-right).
/// One closed outline, so `strokeBorder` draws no seam at the tail.
/// Leave `tailWidth` of free space on the tail side: pad the content with `ChatBubbleShape.contentInsets(for:)`.
struct ChatBubbleShape: InsettableShape {
    enum Side: Sendable { case left, right }

    var side: Side
    var tailWidth: CGFloat = 7
    var inset: CGFloat = 0

    init(_ side: Side, tailWidth: CGFloat = 7) {
        self.side = side
        self.tailWidth = tailWidth
    }

    /// Text padding inside the bubble, with room for the tail.
    static func contentInsets(for side: Side, tailWidth: CGFloat = 7) -> EdgeInsets {
        let tail = tailWidth
        return EdgeInsets(
            top: Theme.Spacing.m,
            leading: Theme.Spacing.l + (side == .left ? tail : 0),
            bottom: Theme.Spacing.m,
            trailing: Theme.Spacing.l + (side == .right ? tail : 0)
        )
    }

    func inset(by amount: CGFloat) -> ChatBubbleShape {
        var copy = self
        copy.inset += amount
        return copy
    }

    func path(in rect: CGRect) -> Path {
        let r = rect.insetBy(dx: inset, dy: inset)
        guard r.width > tailWidth * 2, r.height > 8 else { return Path(r) }
        // Draw the left bubble, then mirror it for the right side.
        let local = CGRect(x: 0, y: 0, width: r.width, height: r.height)
        var path = leftPath(in: local)
        if side == .right {
            path = path.applying(CGAffineTransform(scaleX: -1, y: 1).translatedBy(x: -local.width, y: 0))
        }
        return path.applying(CGAffineTransform(translationX: r.minX, y: r.minY))
    }

    private func leftPath(in r: CGRect) -> Path {
        let body = CGRect(x: r.minX + tailWidth, y: r.minY, width: r.width - tailWidth, height: r.height)
        func cx(_ x: CGFloat) -> CGFloat { min(max(0, x - inset), body.width / 2) }
        func cy(_ y: CGFloat) -> CGFloat { min(max(0, y - inset), body.height / 2) }
        // Uneven radii (tl, tr, br) give the hand-cut look. The bottom-left corner is the tail.
        let tl = CGSize(width: cx(18), height: cy(21))
        let tr = CGSize(width: cx(22), height: cy(16))
        let br = CGSize(width: cx(17), height: cy(20))
        let tailRise = min(cy(14), body.height / 2)
        let k: CGFloat = 0.5523

        var p = Path()
        p.move(to: CGPoint(x: body.minX + tl.width, y: body.minY))
        p.addLine(to: CGPoint(x: body.maxX - tr.width, y: body.minY))
        p.addCurve(
            to: CGPoint(x: body.maxX, y: body.minY + tr.height),
            control1: CGPoint(x: body.maxX - tr.width * (1 - k), y: body.minY),
            control2: CGPoint(x: body.maxX, y: body.minY + tr.height * (1 - k))
        )
        p.addLine(to: CGPoint(x: body.maxX, y: body.maxY - br.height))
        p.addCurve(
            to: CGPoint(x: body.maxX - br.width, y: body.maxY),
            control1: CGPoint(x: body.maxX, y: body.maxY - br.height * (1 - k)),
            control2: CGPoint(x: body.maxX - br.width * (1 - k), y: body.maxY)
        )
        // Bottom edge to the tail tip, then a curved return up to the left edge.
        p.addLine(to: CGPoint(x: r.minX, y: r.maxY))
        p.addQuadCurve(
            to: CGPoint(x: body.minX, y: body.maxY - tailRise),
            control: CGPoint(x: body.minX - tailWidth * 0.1, y: body.maxY - tailRise * 0.25)
        )
        p.addLine(to: CGPoint(x: body.minX, y: body.minY + tl.height))
        p.addCurve(
            to: CGPoint(x: body.minX + tl.width, y: body.minY),
            control1: CGPoint(x: body.minX, y: body.minY + tl.height * (1 - k)),
            control2: CGPoint(x: body.minX + tl.width * (1 - k), y: body.minY)
        )
        p.closeSubpath()
        return p
    }
}

extension View {
    /// Chat bubble surface: fill and 2 pt ink outline on `ChatBubbleShape`.
    /// Penny bubbles use `surface`, user bubbles use an area colour (the caller picks `fill`).
    func llChatBubble(_ side: ChatBubbleShape.Side, fill: Color = Theme.Palette.surface) -> some View {
        padding(ChatBubbleShape.contentInsets(for: side))
            .background {
                ZStack {
                    ChatBubbleShape(side).fill(fill)
                    ChatBubbleShape(side).strokeBorder(Theme.Palette.ink, lineWidth: Theme.chipOutline)
                }
            }
            .contentShape(ChatBubbleShape(side))
    }
}

#Preview("Chat bubbles") {
    VStack(alignment: .leading, spacing: Theme.Spacing.m) {
        Text(verbatim: "Yes, for about 4 months. Your savings cover your bills and mortgage until April.")
            .font(.llBody)
            .llChatBubble(.left)
        Text(verbatim: "What if I lose my job?")
            .font(.llBody)
            .foregroundStyle(Theme.Palette.onArea)
            .llChatBubble(.right, fill: Theme.Palette.work)
            .frame(maxWidth: .infinity, alignment: .trailing)
    }
    .padding()
    .background(Theme.Palette.paper)
}
