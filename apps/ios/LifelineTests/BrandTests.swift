import Testing
@testable import Lifeline

@Test func brandName() {
    #expect(Brand.productName == "Lifeline")
    #expect(Brand.demoPaymentLabel == "Demo payment")
}
