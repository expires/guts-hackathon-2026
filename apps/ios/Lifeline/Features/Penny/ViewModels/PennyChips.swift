import Foundation

/// The student's numbers that Penny's starter chips use. Built from the forecast and this month's spending.
struct PennyChipData: Equatable, Sendable {
    /// Weekly budget from the forecast (`per_week`). Nil or 0 skips the "afford" chip.
    var perWeek: Double?
    /// Biggest spending category this month, without rent, bills and transfers ("Eating out").
    var biggestCategory: String?
    /// "Student Finance England loan". Nil when there is no next money.
    var nextMoneyLabel: String?
    /// The day the next money arrives.
    var nextMoneyDate: Date?
    /// The forecast's today.
    var today: Date
}

/// Starter chips from the student's data (BOSS request, V3). Every amount comes from the data or is a fixed
/// example in the template (£20 less, a £60 night out). No data: the general student chips.
enum PennyChips {
    /// Categories that are not day-to-day choices, so a chip about them makes no sense.
    static let skippedCategories: Set<String> = [
        "housing", "bills", "subscriptions", "transfers", "income", "savings", "cash", "fees", "other", "education",
    ]

    static func data(forecast: Forecast, spending: SpendingResponse?) -> PennyChipData {
        let biggest = spending?.categories
            .filter { !skippedCategories.contains($0.category.rawValue) && $0.amount > 0 }
            .max { $0.amount < $1.amount }
        // Optional or not in the generated type: promote to an optional either way.
        let next: Components.Schemas.NextMoney? = forecast.nextMoney
        let hasNext = forecast.state.rawValue != "no_next_money"
        return PennyChipData(
            perWeek: forecast.perWeek > 0 ? forecast.perWeek : nil,
            biggestCategory: biggest?.label,
            nextMoneyLabel: hasNext ? next?.label : nil,
            nextMoneyDate: hasNext ? next.flatMap { day($0.date) } : nil,
            today: day(forecast.today) ?? Date()
        )
    }

    /// Up to 4 chips. `whatIfFirst` (chat opened from the forecast) puts the what-if chips first.
    static func chips(_ data: PennyChipData, whatIfFirst: Bool = false) -> [String] {
        let category = data.biggestCategory.map(lowerFirst)
        var afford: String?
        if let perWeek = data.perWeek, let category {
            afford = L10n.tr("Can I afford \(Money.format(roundedShare(perWeek))) on \(category) this week?")
        }
        var late: String?
        if let label = data.nextMoneyLabel?.trimmingCharacters(in: .whitespaces), !label.isEmpty {
            late = L10n.tr("What if my \(lowerFirst(label)) is a week late?")
        }
        var less: String?
        if let category {
            less = L10n.tr("What if I spend \(Money.format(20)) less on \(category) a week?")
        }
        var nightOut: String?
        if let date = nightOutDate(today: data.today, before: data.nextMoneyDate) {
            nightOut = L10n.tr("Can I afford a \(Money.format(60)) night out on \(dayText(date))?")
        }
        let ordered = whatIfFirst ? [late, less, afford, nightOut] : [afford, late, less, nightOut]
        return Array(ordered.compactMap { $0 }.prefix(4))
    }

    /// About 10% of the weekly budget, to the nearest £5, at least £5.
    static func roundedShare(_ perWeek: Double) -> Double {
        max(5, (perWeek * 0.1 / 5).rounded() * 5)
    }

    /// The first Friday or Saturday from tomorrow that is before the next money. Nil when there is none.
    static func nightOutDate(today: Date, before next: Date?) -> Date? {
        guard let next else { return nil }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC") ?? .gmt
        for offset in 1...14 {
            guard let date = calendar.date(byAdding: .day, value: offset, to: today), date < next else { return nil }
            let weekday = calendar.component(.weekday, from: date)
            if weekday == 6 || weekday == 7 { return date }
        }
        return nil
    }

    /// "Sat 24 Oct" in the app language.
    static func dayText(_ date: Date) -> String {
        let out = DateFormatter()
        out.locale = Locale(identifier: AppLanguage.current.rawValue)
        out.timeZone = TimeZone(identifier: "UTC")
        out.setLocalizedDateFormatFromTemplate("EEE d MMM")
        return out.string(from: date)
    }

    static func day(_ iso: String?) -> Date? {
        guard let iso else { return nil }
        let parser = DateFormatter()
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.timeZone = TimeZone(identifier: "UTC")
        parser.dateFormat = "yyyy-MM-dd"
        return parser.date(from: iso)
    }

    /// "Pay from the bar job" -> "pay from the bar job"; "Student Finance England loan" stays (a name).
    /// Only the first letter of a common first word is lowered.
    static func lowerFirst(_ text: String) -> String {
        let common: Set<String> = [
            "pay", "wages", "salary", "bursary", "money", "allowance", "loan", "maintenance", "eating", "groceries",
            "transport", "shopping", "entertainment", "health", "travel", "personal", "gifts", "takeaways", "nights",
        ]
        guard let first = text.split(separator: " ").first, common.contains(first.lowercased()) else { return text }
        return text.prefix(1).lowercased() + text.dropFirst()
    }
}
