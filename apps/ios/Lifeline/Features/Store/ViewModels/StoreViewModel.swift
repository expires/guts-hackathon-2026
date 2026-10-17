import Foundation
import Observation

// Minimal ViewModel created by W6 in the ADR 0011 restructure. W7 owns it and adds StoreKit 2.

/// Paid extras. DEMO ONLY: every screen shows "Demo payment". Lessons are never paywalled.
@MainActor
@Observable
final class StoreViewModel {
    private let session: GameSession
    private(set) var purchasing: String?
    private(set) var message: String?
    private(set) var selectedID: String? = PurchaseProduct.lifeline_rewindpass.rawValue
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    static let catalog: [(product: PurchaseProduct, emoji: String, title: String, detail: String)] = [
        (.lifeline_rewindpass, "⏪", "Rewind Pass", "Go back to any past choice as often as you like."),
        (.lifeline_godmode, "🧙", "God Mode", "Choose any job, pay, town and wealth."),
        (.lifeline_bossmode, "🏢", "Boss Mode", "Start a business with Companies House data."),
    ]

    init(session: GameSession) {
        self.session = session
    }

    var state: StoreViewState {
        Self.makeState(
            owned: owned,
            purchasing: purchasing,
            message: message,
            selectedID: selectedID
        )
    }

    private var owned: Set<String> {
        var set = Set<String>()
        if session.hasRewindPass { set.insert(PurchaseProduct.lifeline_rewindpass.rawValue) }
        if session.ownsGodMode { set.insert(PurchaseProduct.lifeline_godmode.rawValue) }
        return set
    }

    var actions: StoreActions {
        StoreActions(
            onBuy: { [weak self] id in Task { await self?.buy(id) } },
            onClose: { [weak self] in self?.onClose() },
            onSelect: { [weak self] id in self?.selectedID = id },
            onRestore: { [weak self] in self?.restore() }
        )
    }

    /// Demo purchases live in this session. Restore reports what this session owns.
    func restore() {
        let names = Self.catalog.filter { owned.contains($0.product.rawValue) }.map(\.title)
        message = names.isEmpty
            ? "No demo purchases to restore. Demo purchases last for this session only."
            : "Restored: " + names.joined(separator: ", ") + "."
    }

    func buy(_ id: String) async {
        guard let product = PurchaseProduct(rawValue: id), purchasing == nil else { return }
        purchasing = id
        defer { purchasing = nil }
        do {
            let response = try await session.client.verifyPurchase(product: product)
            guard response.active else {
                message = "The purchase did not go through."
                return
            }
            switch response.entitlement {
            case .rewindPass: session.hasRewindPass = true
            case .godMode: session.ownsGodMode = true
            case .bossMode: break
            }
            message = "Unlocked (\(response.label))."
        } catch {
            message = APIError.map(error).userMessage
        }
    }

    /// `LLIcon` raw value per product.
    static let icons: [String: String] = [
        PurchaseProduct.lifeline_rewindpass.rawValue: "rewind",
        PurchaseProduct.lifeline_godmode.rawValue: "face-blue-hair",
        PurchaseProduct.lifeline_bossmode.rawValue: "job",
    ]

    /// "£0.99".
    static func priceText(_ price: Double) -> String {
        price.formatted(.currency(code: "GBP").locale(Money.locale).precision(.fractionLength(2)))
    }

    static func makeState(
        owned: Set<String>,
        purchasing: String?,
        message: String?,
        selectedID: String? = nil,
        prices: [String: Double] = StoreFixtures.demoPrices
    ) -> StoreViewState {
        var state = StoreViewState(
            products: catalog.map {
                .init(
                    id: $0.product.rawValue,
                    emoji: $0.emoji,
                    title: $0.title,
                    detail: $0.detail,
                    priceText: prices[$0.product.rawValue].map(priceText) ?? "Demo",
                    isOwned: owned.contains($0.product.rawValue),
                    isPurchasing: purchasing == $0.product.rawValue,
                    icon: icons[$0.product.rawValue] ?? "demo-pay",
                    price: prices[$0.product.rawValue]
                )
            },
            demoLabel: Brand.demoPaymentLabel,
            lessonsNote: "Lessons are always free.",
            message: message
        )
        state.selectedID = selectedID ?? state.products.first(where: { !$0.isOwned })?.id
        if let product = state.selected {
            state.buyTitle = product.isOwned
                ? "\(product.title) owned"
                : "Buy \(product.title) · \(product.priceText) · demo"
            state.canBuy = !product.isOwned && purchasing == nil
        } else {
            state.buyTitle = "Choose an extra"
            state.canBuy = false
        }
        return state
    }
}
