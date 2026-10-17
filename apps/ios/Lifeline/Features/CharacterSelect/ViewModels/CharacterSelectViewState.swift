import Foundation

struct CharacterSelectViewState: Equatable, Sendable {
    enum CardKind: Equatable, Sendable {
        case playYourself
        case preset
        case random
        case godMode
    }

    struct Card: Equatable, Sendable, Identifiable {
        /// Stable id. Also the accessibility identifier suffix: `character.<id>`.
        var id: String
        var kind: CardKind
        var emoji: String
        var title: String
        var subtitle: String
        /// For example "£24,800 a year".
        var detail: String?
        var badge: String?
        var isLocked: Bool
    }

    var phase: LoadPhase
    var intro: String
    /// Order: Play yourself, presets, Random, God Mode.
    var cards: [Card]
    var usesSampleData: Bool
    /// For example "Penny 1.0 (1)". Long-press opens the debug menu in Debug builds.
    var versionText: String
}

struct CharacterSelectActions {
    var onSelect: @MainActor (String) -> Void = { _ in }
    var onRetry: @MainActor () -> Void = {}
    var onOpenRooms: @MainActor () -> Void = {}
    var onOpenStore: @MainActor () -> Void = {}
    var onOpenSources: @MainActor () -> Void = {}
    var onVersionLongPress: @MainActor () -> Void = {}
    /// Back to Play when Life is opened from the Play tab. Nil hides the button.
    var onClose: (@MainActor () -> Void)?

    static var noop: Self { .init() }
}
