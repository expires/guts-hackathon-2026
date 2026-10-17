import SwiftUI

/// Generic loading state.
struct LoadingStateView: View {
    let state: LoadingViewState

    var body: some View {
        // Skeleton rows in the shape of a list, never a spinner (ADR 0060). VoiceOver reads the message.
        SkeletonList(rows: 4, showsCard: true)
            .padding(Theme.Spacing.margin)
            .frame(maxWidth: .infinity, alignment: .top)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(state.message)
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
