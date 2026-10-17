import SwiftUI

/// One small grey line for Penny's current tool step ("Checking Bank of England…").
/// A new label replaces the old one in place (cross-fade). nil keeps the line's height but shows nothing,
/// so the chat does not jump when steps start and stop.
struct ToolStepLine: View {
    let text: String?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(_ text: String?) {
        self.text = text
    }

    var body: some View {
        Text(text ?? " ")
            .font(.llLabel)
            .foregroundStyle(Theme.Palette.muted)
            .lineLimit(1)
            .truncationMode(.tail)
            .frame(maxWidth: .infinity, alignment: .leading)
            .opacity(text == nil ? 0 : 1)
            .contentTransition(reduceMotion ? .identity : .opacity)
            .animation(Motion.crossFade, value: text)
            .accessibilityHidden(text == nil)
            .accessibilityAddTraits(.updatesFrequently)
    }
}

#Preview("Tool step") {
    VStack(alignment: .leading) {
        ToolStepLine("Checking Bank of England…")
        ToolStepLine(nil)
        ToolStepLine("Replaying 2022…")
    }
    .padding()
    .background(Theme.Palette.paper)
}
