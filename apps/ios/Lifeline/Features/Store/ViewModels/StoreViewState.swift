import Foundation

struct StoreViewState: Equatable, Sendable {
    struct Product: Equatable, Sendable, Identifiable {
        /// StoreKit product id, for example "lifeline.rewindpass".
        var id: String
        var emoji: String
        var title: String
        var detail: String
        /// Price label. "Demo" until StoreKit prices load.
        var priceText: String
        var isOwned: Bool
        var isPurchasing: Bool
    }

    var products: [Product]
    /// Always "Demo payment".
    var demoLabel: String
    /// "Lessons are always free."
    var lessonsNote: String
    /// Result of the last purchase, or an error.
    var message: String?
}

struct StoreActions {
    var onBuy: @MainActor (String) -> Void = { _ in }
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
