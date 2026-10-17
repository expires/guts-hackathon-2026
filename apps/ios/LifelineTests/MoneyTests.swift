import Testing
@testable import Lifeline

@Suite("Money formatting")
struct MoneyTests {
    @Test(arguments: [
        (12_500.0, "£12,500"),
        (-11_000.0, "-£11,000"),
        (0.0, "£0"),
        (1_234_567.4, "£1,234,567"),
        (99.6, "£100"),
    ])
    func format(value: Double, expected: String) {
        #expect(Money.format(value) == expected)
    }

    @Test func signed() {
        #expect(Money.signed(600) == "+£600")
        #expect(Money.signed(-540) == "-£540")
        #expect(Money.signed(0) == "£0")
    }

    @Test(arguments: [
        (950.0, "£950"),
        (12_500.0, "£12.5k"),
        (12_000.0, "£12k"),
        (-1_200_000.0, "-£1.2m"),
        (-11_000.0, "-£11k"),
    ])
    func compact(value: Double, expected: String) {
        #expect(Money.compact(value) == expected)
    }

    @Test func spoken() {
        #expect(Money.spoken(-11_000) == "minus 11,000 pounds")
        #expect(Money.spoken(4_100) == "4,100 pounds")
    }
}
