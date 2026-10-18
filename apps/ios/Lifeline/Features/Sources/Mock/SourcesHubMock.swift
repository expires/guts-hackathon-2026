import Foundation

/// The sources hub for `MockClient`, previews and tests (ADR 0073): the eight student-facing sources with sample
/// values in the shape of `GET /v1/sources/hub`. English only (the server translates the live response).
enum SourcesHubMock {
    static var hub: SourcesHub { hub(now: Date()) }

    /// `now` sets the update times, so the relative times read "5 min ago" and so on.
    static func hub(now: Date) -> SourcesHub {
        func ago(_ minutes: Double) -> Date { now.addingTimeInterval(-minutes * 60) }
        func value(_ label: String, _ value: String, _ asOf: String?) -> HubValue {
            HubValue(label: label, value: value, asOf: asOf)
        }
        let sources: [HubSource] = [
            HubSource(
                id: "statement", name: "Your statement", kind: .statement, status: .cached, updatedAt: ago(60 * 26),
                gives: "Your balance, bills, pay and how you usually spend.",
                usedIn: ["Money", "The maths", "Penny"],
                latest: [value("Statement covers", "1 Jul to 16 Oct", "16 Oct 2026"), value("Payments read", "412", nil)]
            ),
            HubSource(
                id: "facts", name: "Official facts", kind: .officialFacts, status: .cached, updatedAt: ago(60 * 24 * 12),
                gives: "Student loan, bursary and grant amounts from gov.uk, SAAS and Student Finance.",
                usedIn: ["Your next money", "Penny"],
                latest: [
                    value("Maintenance loan, away from home, outside London", "£10,544 a year", "2025/26"),
                    value("SAAS Young Students' Bursary, top rate", "£2,000 a year", "2025/26"),
                ],
                url: "https://www.gov.uk/student-finance"
            ),
            HubSource(
                id: "boe", name: "Bank of England", kind: .live, status: .live, updatedAt: ago(5),
                gives: "Interest rates for saving and borrowing.",
                usedIn: ["One thing that helps", "The maths"],
                latest: [value("Easy-access savings rate", "2.06%", "Sep 2026"), value("Bank Rate", "3.75%", "Sep 2026")],
                url: "https://www.bankofengland.co.uk/boeapps/database"
            ),
            HubSource(
                id: "ons", name: "ONS", kind: .live, status: .live, updatedAt: ago(42),
                gives: "Price rises (inflation), so Penny can check your budget against them.",
                usedIn: ["Your usual spending", "Penny"],
                latest: [value("Prices, 12 months (CPI)", "3.8%", "Aug 2026"), value("Food prices, 12 months", "4.2%", "Aug 2026")],
                url: "https://www.ons.gov.uk/economy/inflationandpriceindices"
            ),
            HubSource(
                id: "nomis", name: "Nomis", kind: .live, status: .cached, updatedAt: ago(60 * 24 * 3),
                gives: "Typical pay for part-time work near you.",
                usedIn: ["Penny"],
                latest: [value("Median hourly pay, part-time", "£12.60", "2025")],
                url: "https://www.nomisweb.co.uk"
            ),
            HubSource(
                id: "octopus", name: "Octopus Energy", kind: .live, status: .live, updatedAt: ago(18),
                gives: "Gas and electricity prices for your bills.",
                usedIn: ["Bills", "Penny"],
                latest: [value("Electricity unit rate", "24.9p per kWh", "Oct 2026"), value("Gas unit rate", "6.3p per kWh", "Oct 2026")],
                url: "https://octopus.energy/tariffs/"
            ),
            HubSource(
                id: "frankfurter", name: "Frankfurter", kind: .live, status: .live, updatedAt: ago(90),
                gives: "Exchange rates, for money sent from home in another currency.",
                usedIn: ["Your next money", "Penny"],
                latest: [value("£1 in euros", "€1.16", "17 Oct 2026"), value("£1 in US dollars", "$1.33", "17 Oct 2026")],
                url: "https://frankfurter.dev"
            ),
            HubSource(
                id: "boe-mpc", name: "Bank of England MPC dates", kind: .live, status: .cached, updatedAt: ago(60 * 24 * 2),
                gives: "When interest rates may change next.",
                usedIn: ["Penny"],
                latest: [value("Next rate decision", "5 Nov 2026", nil)],
                url: "https://www.bankofengland.co.uk/monetary-policy/upcoming-mpc-dates"
            ),
        ]
        return SourcesHub(
            summary: "Penny uses your statement plus 7 live UK sources. Here is what each one does.",
            liveCount: 7,
            sources: sources
        )
    }
}
