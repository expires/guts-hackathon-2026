import SwiftUI
import UIKit

/// UIKit appearance for system bars, so navigation titles use the handoff fonts and colours.
enum LLAppearance {
    @MainActor static func apply() {
        LLFont.registerAll()
        let ink = UIColor(Theme.Palette.ink)
        let nav = UINavigationBarAppearance()
        nav.configureWithOpaqueBackground()
        nav.backgroundColor = UIColor(Theme.Palette.paper)
        nav.shadowColor = .clear
        if let title = UIFont(name: LLFont.display, size: 24), let large = UIFont(name: LLFont.display, size: 40) {
            nav.titleTextAttributes = [.font: UIFontMetrics(forTextStyle: .title2).scaledFont(for: title), .foregroundColor: ink]
            nav.largeTitleTextAttributes = [.font: UIFontMetrics(forTextStyle: .largeTitle).scaledFont(for: large), .foregroundColor: ink]
        }
        if let body = UIFont(name: LLFont.bodyBold, size: 17) {
            let button = UIBarButtonItemAppearance()
            button.normal.titleTextAttributes = [.font: UIFontMetrics(forTextStyle: .body).scaledFont(for: body), .foregroundColor: ink]
            nav.buttonAppearance = button
            nav.doneButtonAppearance = button
        }
        UINavigationBar.appearance().standardAppearance = nav
        UINavigationBar.appearance().scrollEdgeAppearance = nav
        UINavigationBar.appearance().compactAppearance = nav
        UINavigationBar.appearance().tintColor = ink
    }
}
