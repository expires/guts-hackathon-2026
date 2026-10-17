import SwiftUI

/// Small link back to the hub: "Your next move: Take a tracker". Money home is the hub (ADR 0042).
struct NextMoveLinkRow: View {
    let text: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.s) {
                PennyView(mood: .smiling, size: 28)
                Text(text)
                    .font(.llBodyBold)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
                Chevron()
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.l)
            .padding(.vertical, Theme.Spacing.s)
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .inkSurface(.badge, lineWidth: Theme.chipOutline)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(text)
        .accessibilityHint("Opens your next move on the Money tab")
        .accessibilityIdentifier("nextMoveLink")
    }
}

#Preview("Link · light") { NextMoveLinkRow(text: "Your next move: Take a tracker") {}.padding().paperBackground() }
#Preview("Link · dark") { NextMoveLinkRow(text: "Your next move: Take a tracker") {}.padding().paperBackground().previewDark() }
#Preview("Link · AX3") { NextMoveLinkRow(text: "Your next move: Take a tracker") {}.padding().paperBackground().previewLargeType() }
