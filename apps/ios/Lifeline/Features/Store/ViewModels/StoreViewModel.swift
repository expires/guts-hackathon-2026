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
            message: message
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
            onClose: { [weak self] in self?.onClose() }
        )
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

    static func makeState(owned: Set<String>, purchasing: String?, message: String?) -> StoreViewState {
        StoreViewState(
            products: catalog.map {
                .init(
                    id: $0.product.rawValue,
                    emoji: $0.emoji,
                    title: $0.title,
                    detail: $0.detail,
                    priceText: "Demo",
                    isOwned: owned.contains($0.product.rawValue),
                    isPurchasing: purchasing == $0.product.rawValue
                )
            },
            demoLabel: Brand.demoPaymentLabel,
            lessonsNote: "Lessons are always free.",
            message: message
        )
    }
}
