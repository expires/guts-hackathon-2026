import SwiftUI

/// Generic loading state.
struct LoadingStateView: View {
    let state: LoadingViewState

    var body: some View {
        VStack(spacing: Theme.Spacing.m) {
            ProgressView()
                .controlSize(.large)
            Text(state.message)
                .font(.llBody)
                .foregroundStyle(Theme.Palette.muted)
        }
        .padding(Theme.Spacing.xl)
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("loading.state")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Loading · light") {
    LoadingStateView(state: Fixtures.loading)
}

#Preview("Loading · dark") {
    LoadingStateView(state: Fixtures.loading).previewDark()
}

#Preview("Loading · AX3") {
    LoadingStateView(state: Fixtures.loading).previewLargeType()
}
