import Foundation

/// The other path for a mortgage decision, as fixture data (ADR 0026 placeholders).
/// The contract has no "other choice" for a past decision yet, so the Rewind card reads this table.
/// Rates are Bank of England quoted rates for Sep 2021, typed in by hand (not fetched).
struct RewindAlternative: Equatable, Sendable {
    var title: String
    /// Annual rate in percent.
    var ratePercent: Double
    var source: SourceChipState
    /// Monthly payment, only when the fixture carries it with its own source. Nil omits the line.
    /// The app never calculates a mortgage payment.
    var monthlyPayment: SourcedAmount? = nil
    /// Years until the next choice.
    var fixYears: Int
}

/// A GBP amount plus the source that gives it.
struct SourcedAmount: Equatable, Sendable {
    var amount: Double
    var source: SourceChipState
}

enum RewindAlternatives {
    /// 2021 five-year fix: 1.28% (BoE IUMBV42, Sep 2021). User placeholder, ADR 0026.
    static let fiveYearFix2021 = RewindAlternative(
        title: "Fix for 5 years",
        ratePercent: 1.28,
        source: SourceChipState(
            id: "boe.IUMBV42",
            name: "BoE IUMBV42, Sep 2021",
            status: .mock,
            note: "Sep 2021 rate typed in by hand. Not fetched from the Bank of England."
        ),
        fixYears: 5
    )

    /// 2021 two-year fix: 1.20% (handoff "Data used", BoE IUMBV34, Sep 2021).
    static let twoYearFix2021 = RewindAlternative(
        title: "Fix for 2 years",
        ratePercent: 1.20,
        source: SourceChipState(
            id: "boe.IUMBV34",
            name: "BoE IUMBV34, Sep 2021",
            status: .mock,
            note: "Sep 2021 rate from the design handoff. Not fetched from the Bank of England."
        ),
        fixYears: 2
    )

    /// Keyed by the choice the player took (backend ids from the `home.deal_ends` template).
    static let byChoice: [String: RewindAlternative] = [
        "fix_2y": fiveYearFix2021,
        "fix_5y": twoYearFix2021,
        "tracker": fiveYearFix2021,
        "svr": fiveYearFix2021,
    ]
}
