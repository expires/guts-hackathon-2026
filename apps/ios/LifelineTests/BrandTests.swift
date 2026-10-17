import Testing
@testable import Lifeline

/// ADR 0040: the product is "Penny".
@Test func brandName() {
    #expect(Brand.productName == "Penny")
    #expect(Brand.tagline == "Your money, played forward.")
    #expect(Brand.demoPaymentLabel == "Demo payment")
}
