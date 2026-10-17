import Foundation

/// Labelled sample data for the Insights screen. Used by `MockClient`, fixtures and the Playground.
/// Everything here is made up. The sample has 4 complete months, so asking for 6 or 12 shows the
/// "Based on your last 4 months" note, the same way a real short history does.
enum SampleInsights {
    private static let months = ["2026-06", "2026-07", "2026-08", "2026-09"]
    private static let income: [Double] = [2_480, 2_480, 2_520, 2_480]
    private static let spend: [Double] = [1_905.40, 2_012.75, 1_788.20, 1_864.60]

    private struct Cat {
        var id: String
        var label: String
        var emoji: String
        var values: [Double]
    }

    private static let cats: [Cat] = [
        Cat(id: "housing", label: "Housing", emoji: "🏠", values: [850, 850, 850, 850]),
        Cat(id: "groceries", label: "Groceries", emoji: "🛒", values: [301.20, 322.40, 289.10, 318.55]),
        Cat(id: "eating_out", label: "Eating out", emoji: "🍔", values: [168.50, 240.30, 151.80, 176.25]),
        Cat(id: "transport", label: "Transport", emoji: "🚆", values: [112.00, 118.50, 104.00, 121.80]),
        Cat(id: "shopping", label: "Shopping", emoji: "🛍️", values: [96.40, 140.20, 82.30, 61.00]),
        Cat(id: "subscriptions", label: "Subscriptions", emoji: "🔁", values: [37.98, 37.98, 37.98, 37.98]),
        Cat(id: "entertainment", label: "Entertainment", emoji: "🎬", values: [58.00, 64.00, 61.50, 49.50]),
    ]

    static func make(months requested: Int) -> SpendingInsights {
        let used = max(2, min(requested, months.count))
        let slice = months.count - used
        let m = Array(months.suffix(used))
        let inc = Array(income.suffix(used))
        let spd = Array(spend.suffix(used))
        let totalSpend = spd.reduce(0, +)
        let totalIncome = inc.reduce(0, +)
        let hasPrior = used <= 2
        let categories = cats.map { cat -> InsightCategoryValue in
            let amount = cat.values.suffix(used).reduce(0, +)
            return InsightCategoryValue(cat: cat, amount: amount, used: used, hasPrior: hasPrior, slice: slice)
        }
        return SpendingInsights(
            meta: FinanceMeta(dataStatus: .mock, source: "fixtures", asOf: "2026-10-17", label: "Sample data"),
            windowMonths: used,
            requestedMonths: requested,
            startMonth: m.first,
            endMonth: m.last,
            note: used < requested ? "Based on your last \(used) months" : nil,
            totalIncome: totalIncome,
            totalSpend: (totalSpend * 100).rounded() / 100,
            monthly: m.indices.map { .init(month: m[$0], income: inc[$0], spend: spd[$0], net: ((inc[$0] - spd[$0]) * 100).rounded() / 100) },
            categories: categories.map { value in
                .init(
                    category: .init(rawValue: value.cat.id)!, label: value.cat.label, emoji: value.cat.emoji,
                    amount: (value.amount * 100).rounded() / 100, share: (value.amount / totalSpend * 10_000).rounded() / 10_000,
                    monthlyAverage: (value.amount / Double(used) * 100).rounded() / 100, changePct: value.change
                )
            },
            categoryMonths: m,
            categoryByMonth: cats.map {
                .init(category: .init(rawValue: $0.id)!, label: $0.label, emoji: $0.emoji, values: Array($0.values.suffix(used)))
            },
            topMerchants: [
                .init(merchant: "Landlord", category: .housing, emoji: "🏠", amount: 850 * Double(used), count: used),
                .init(merchant: "Tesco", category: .groceries, emoji: "🛒", amount: 164.35 * Double(used), count: 7 * used),
                .init(merchant: "TfL", category: .transport, emoji: "🚆", amount: 91.20 * Double(used), count: 14 * used),
                .init(merchant: "Pret A Manger", category: .eatingOut, emoji: "🍔", amount: 48.75 * Double(used), count: 9 * used),
                .init(merchant: "Amazon", category: .shopping, emoji: "🛍️", amount: 41.10 * Double(used), count: 3 * used),
            ],
            subscriptions: .init(
                monthlyTotal: 37.98, annualTotal: 455.76,
                items: [
                    .init(merchant: "Netflix", emoji: "📺", monthlyCost: 12.99, annualCost: 155.88),
                    .init(merchant: "PureGym", emoji: "🏋️", monthlyCost: 24.99, annualCost: 299.88),
                ]
            ),
            unusual: [
                .init(id: "tx_zara", date: "2026-07-18", merchant: "Zara", category: .shopping, emoji: "🛍️", amount: 148.00, typical: 32.50),
                .init(id: "tx_dinner", date: "2026-07-26", merchant: "Dishoom", category: .eatingOut, emoji: "🍔", amount: 96.40, typical: 18.20),
            ],
            patterns: .init(
                weekendShare: 0.46, weekdayShare: 0.54, averageDailySpend: 62.15, biggestWeekday: "Saturday",
                biggestDay: "2026-07-26", biggestDayAmount: 148.40,
                byWeekday: [
                    .init(weekday: "Monday", amount: 212.40), .init(weekday: "Tuesday", amount: 180.10),
                    .init(weekday: "Wednesday", amount: 205.80), .init(weekday: "Thursday", amount: 231.60),
                    .init(weekday: "Friday", amount: 298.30), .init(weekday: "Saturday", amount: 412.70),
                    .init(weekday: "Sunday", amount: 268.20),
                ]
            ),
            insights: [
                "Housing is your biggest spend: £\(Int(850 * Double(used)).formatted()), \(Int((850 * Double(used) / totalSpend * 100).rounded()))% of the £\(Int(totalSpend.rounded()).formatted()) you spent.",
                "You earned more than you spent in all of the last \(used) months, £\(Int((totalIncome - totalSpend).rounded()).formatted()) in total.",
                "Your 2 subscriptions cost £37.98 a month, £455.76 a year.",
                "46% of your treat spending happens at weekends.",
                "2 payments were more than 3 times the usual for their type.",
            ]
        )
    }

    private struct InsightCategoryValue {
        var cat: Cat
        var amount: Double
        var used: Int
        var hasPrior: Bool
        var slice: Int

        /// Sample change vs the months before: only when the window leaves room for them (2 months of 4).
        var change: Double? {
            guard hasPrior else { return nil }
            let now = cat.values.suffix(used).reduce(0, +)
            let before = cat.values.prefix(slice).suffix(used).reduce(0, +)
            guard before > 0 else { return nil }
            return ((now - before) / before * 1_000).rounded() / 10
        }
    }
}
