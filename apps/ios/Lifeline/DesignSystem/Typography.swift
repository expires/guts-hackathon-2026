import CoreText
import SwiftUI

/// Fonts from the handoff: Bricolage Grotesque 800 (numbers, titles) and Atkinson Hyperlegible 400/700 (body).
/// Bundled under `Resources/Fonts` (SIL OFL 1.1, see `Resources/Credits.json`), registered at launch.
/// Bricolage is a static instance of the variable font at weight 800, width 100, optical size 36.
/// Atkinson is a modified build (family "Atkinson Hyperlegible LL"): its zero glyph is drawn from "O"
/// so zeros are never slashed (user request). Allowed by the OFL; the licence names no Reserved Font Name.
enum LLFont {
    static let display = "BricolageGrotesque-36ptExtraBold"
    static let body = "AtkinsonHyperlegibleLL-Regular"
    static let bodyBold = "AtkinsonHyperlegibleLL-Bold"
    static let files = ["BricolageGrotesque-ExtraBold", "AtkinsonHyperlegible-Regular", "AtkinsonHyperlegible-Bold"]

    /// Registers the bundled fonts once. Safe to call many times (app launch, previews, tests).
    static func registerAll() {
        _ = registered
    }

    /// Lazy and thread-safe. The font accessors below touch it, so previews work without the app's `init`.
    static let registered: Bool = {
        for name in files {
            guard let url = Bundle.main.url(forResource: name, withExtension: "ttf") else { continue }
            CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
        }
        return true
    }()
}

/// The 4 sizes: 40 (hero numbers, age), 24 (titles), 17 (body, buttons), 13 (labels).
/// Each scales with Dynamic Type.
extension Font {
    /// 40, Bricolage 800. Hero numbers and age.
    static var llHero: Font { LLFont.registerAll(); return .custom(LLFont.display, size: 40, relativeTo: .largeTitle) }
    /// 24, Bricolage 800. Titles and year headers.
    /// Compact screen title (ADR 0048): 22 pt display, scales with Dynamic Type.
    static var llScreenHeader: Font { LLFont.registerAll(); return .custom(LLFont.display, size: 22, relativeTo: .title2) }
    static var llTitle: Font { LLFont.registerAll(); return .custom(LLFont.display, size: 24, relativeTo: .title2) }
    /// 17, Atkinson 400. Body.
    static var llBody: Font { LLFont.registerAll(); return .custom(LLFont.body, size: 17, relativeTo: .body) }
    /// 17, Atkinson 700. Buttons and row titles.
    static var llBodyBold: Font { LLFont.registerAll(); return .custom(LLFont.bodyBold, size: 17, relativeTo: .body) }
    /// 13, Atkinson 400. Captions.
    static var llLabel: Font { LLFont.registerAll(); return .custom(LLFont.body, size: 13, relativeTo: .footnote) }
    /// 13, Atkinson 700. Labels, chips, eyebrows.
    static var llLabelBold: Font { LLFont.registerAll(); return .custom(LLFont.bodyBold, size: 13, relativeTo: .footnote) }
}

extension View {
    /// Eyebrow label: 13 bold, uppercase, 0.08 em tracking.
    func llEyebrow() -> some View {
        font(.llLabelBold).textCase(.uppercase).tracking(1.04)
    }
}
