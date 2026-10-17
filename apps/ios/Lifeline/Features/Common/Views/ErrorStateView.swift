import SwiftUI

/// Generic error state with an optional retry button.
struct ErrorStateView: View {
    let state: ErrorViewState
    var onRetry: () -> Void = {}

    var body: some View {
        VStack(spacing: Theme.Spacing.m) {
            LLIconImage(.crash)
                .font(.llHero)
                .foregroundStyle(Theme.Palette.home)
                .accessibilityHidden(true)
            Text(state.title).font(.llBodyBold)
            Text(state.message)
                .font(.llBody)
                .foregroundStyle(Theme.Palette.muted)
                .multilineTextAlignment(.center)
            if state.canRetry {
                Button("Try again", icon: .rewind, action: onRetry)
                    .buttonStyle(.main)
                    .frame(minHeight: Theme.minTarget)
                    .accessibilityIdentifier("error.retry")
            }
        }
        .padding(Theme.Spacing.xl)
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("error.state")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Offline · light") {
    ErrorStateView(state: Fixtures.networkError)
}

#Preview("Offline · dark") {
    ErrorStateView(state: Fixtures.networkError).previewDark()
}

#Preview("Offline · AX3") {
    ErrorStateView(state: Fixtures.networkError).previewLargeType()
}

#Preview("Start age · light") {
    ErrorStateView(state: Fixtures.startAgeError)
}

#Preview("Start age · dark") {
    ErrorStateView(state: Fixtures.startAgeError).previewDark()
}

#Preview("Start age · AX3") {
    ErrorStateView(state: Fixtures.startAgeError).previewLargeType()
}

#Preview("Server · light") {
    ErrorStateView(state: Fixtures.serverError)
}

#Preview("Server · dark") {
    ErrorStateView(state: Fixtures.serverError).previewDark()
}

#Preview("Server · AX3") {
    ErrorStateView(state: Fixtures.serverError).previewLargeType()
}
