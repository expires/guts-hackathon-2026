import SwiftUI

/// Preview helpers. Each View file has one `#Preview` per fixture in light, dark and large Dynamic Type.
extension View {
    /// Dark appearance.
    func previewDark() -> some View {
        preferredColorScheme(.dark)
    }

    /// Accessibility Dynamic Type size (AX3).
    func previewLargeType() -> some View {
        environment(\.dynamicTypeSize, .accessibility3)
    }

    /// Wraps a screen in a navigation stack, as in the app.
    func previewInNavigation() -> some View {
        NavigationStack { self }
    }
}
