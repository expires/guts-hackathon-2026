import SwiftUI

extension EnvironmentValues {
    /// "Sample data" (a sample statement) or "Mock data" (canned data). Set by the screen that knows the data's `meta`.
    @Entry var dataBadgeText: String? = nil
}

/// The data label chip in the handoff style. "Sample data" for sample statements, otherwise "Mock data".
struct DataBadge: View {
    var text: String?
    @Environment(\.dataBadgeText) private var environmentText

    /// PENNY_V3_BUILD.md B4: data tags are gone everywhere; the honesty line replaces them.
    var body: some View { EmptyView() }

}
