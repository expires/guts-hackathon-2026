import Foundation

/// Action menus inside the Life tab (ADR 0016): Job, Assets, People, Money, Activities.
/// The glue attaches the menu bar to `LifeView` with `.safeAreaInset`, so `LifeView` needs no edit.
struct LifeMenuViewState: Equatable, Sendable {
    enum Menu: String, Equatable, Sendable, CaseIterable, Identifiable {
        case job, assets, people, money, activities
        var id: String { rawValue }
    }

    struct Item: Equatable, Sendable, Identifiable {
        var menu: Menu
        var title: String
        var icon: LLIcon
        /// Enabled actions in this menu. 0 hides the badge.
        var count: Int
        var id: Menu { menu }
    }

    var items: [Item]
    var isEnabled: Bool
}

struct LifeMenuActions {
    var onOpen: @MainActor (LifeMenuViewState.Menu) -> Void = { _ in }

    static var noop: Self { .init() }
}
