import SwiftUI

extension EnvironmentValues {
    /// "Sample data" (a sample statement) or "Mock data" (canned data). Set by the screen that knows the data's `meta`.
    @Entry var dataBadgeText: String? = nil
}

/// The data label chip in the handoff style. "Sample data" for sample statements, otherwise "Mock data".
struct DataBadge: View {
    var text: String?
    @Environment(\.dataBadgeText) private var environmentText

    var body: some View {
        let label = text ?? environmentText ?? "Mock data"
        Text(label)
            .font(.llLabelBold)
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, 10)
            .padding(.vertical, 3)
            .inkSurface(.badge, lineWidth: Theme.chipOutline)
            .accessibilityLabel(label == "Sample data"
                ? "Sample data. A made-up student statement, not your bank."
                : "Mock data. Not from your bank or the live server.")
            .accessibilityIdentifier("demoDataBadge")
    }
}
