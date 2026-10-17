import Foundation

/// Demo prices for the paywall (ADR 0026 placeholders). StoreKit wiring is Tier 2, so prices come from here.
/// Every product is labelled "Demo payment". No real money is taken.
enum StoreFixtures {
    static let demoPrices: [String: Double] = [
        PurchaseProduct.lifeline_rewindpass.rawValue: 0.99,
        PurchaseProduct.lifeline_godmode.rawValue: 1.99,
        PurchaseProduct.lifeline_bossmode.rawValue: 2.99,
    ]
}

@MainActor
extension StoreFixtures {
    static var godModeSelected: StoreViewState {
        StoreViewModel.makeState(owned: [], purchasing: nil, message: nil, selectedID: PurchaseProduct.lifeline_godmode.rawValue)
    }
}
