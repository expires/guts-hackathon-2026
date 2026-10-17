import Foundation

/// One central switch for features that are hidden from navigation. The code stays compiled:
/// flip a flag to `true` to bring a feature back. Nothing visible may lead into a hidden feature.
enum AppFeatures {
    /// The Life game: character select, Life shell, Rewind, Summary, Lesson, Concepts, Decision,
    /// Evaluation, Test it, Rooms, Store, Play tab, "Guess my spend" and the You-tab game scores.
    static let game = false
    /// Friends tab. Another agent adds it later (see `AppTab.friends` in RootScreen).
    static let friends = false

    /// Tabs shown in the tab bar, in order.
    static var visibleTabs: [AppTab] {
        AppTab.allCases.filter { tab in
            switch tab {
            case .life, .play: game
            default: true
            }
        }
    }
}
