import SwiftUI

/// Three dots under Penny while she works (ADR 0031 streaming amendment).
/// With Reduce Motion on, the dots do not move: they fade in turn.
struct TypingDots: View {
    var dotSize: CGFloat = 8
    var color: Color = Theme.Palette.muted
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        TimelineView(.periodic(from: .now, by: 0.15)) { context in
            let step = Int(context.date.timeIntervalSinceReferenceDate / 0.15) % 6
            HStack(spacing: dotSize * 0.6) {
                ForEach(0..<3, id: \.self) { index in
                    let active = step / 2 == index
                    Circle()
                        .fill(color)
                        .frame(width: dotSize, height: dotSize)
                        .opacity(reduceMotion ? (active ? 1 : 0.35) : (active ? 1 : 0.55))
                        .offset(y: reduceMotion || !active ? 0 : -dotSize * 0.45)
                        .animation(reduceMotion ? nil : .easeInOut(duration: 0.15), value: step)
                }
            }
            .padding(.vertical, dotSize * 0.5)
        }
        .accessibilityElement()
        .accessibilityLabel("Penny is typing")
    }
}

#Preview("Typing dots") {
    TypingDots()
        .padding()
        .background(Theme.Palette.paper)
}
