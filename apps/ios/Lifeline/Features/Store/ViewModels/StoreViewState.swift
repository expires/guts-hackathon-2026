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
        /// `LLIcon` raw value.
        var icon: String = "demo-pay"
        /// Demo price in GBP from the fixture price list. Nil until known.
        var price: Double? = nil
    }

    var products: [Product]
    /// Always "Demo payment".
    var demoLabel: String
    /// "Lessons are always free."
    var lessonsNote: String
    /// Result of the last purchase, or an error.
    var message: String?
    /// The product the main button buys.
    var selectedID: String? = nil
    /// "Buy Rewind Pass · £0.99".
    var buyTitle: String = ""
    var canBuy: Bool = true

    var selected: Product? { products.first { $0.id == selectedID } }
}

struct StoreActions {
    var onBuy: @MainActor (String) -> Void = { _ in }
    var onClose: @MainActor () -> Void = {}
    var onSelect: @MainActor (String) -> Void = { _ in }
    var onRestore: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
