import SwiftUI

/// Compact type for the four-tab layout (ADR 0048), local to W6's screens.
/// Same families as the design system; both scale with Dynamic Type.
extension Font {
    /// 22, Bricolage 800. Screen titles and greetings.
    static var llScreenTitle: Font { LLFont.registerAll(); return .custom(LLFont.display, size: 22, relativeTo: .title2) }
    /// 15, Atkinson 700. Section headers such as "Coming up".
    static var llSection: Font { LLFont.registerAll(); return .custom(LLFont.bodyBold, size: 15, relativeTo: .subheadline) }
}
