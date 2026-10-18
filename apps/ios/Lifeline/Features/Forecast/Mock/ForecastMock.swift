import Foundation

/// Mock forecast, category and month data for `MockClient`, previews and tests (ADR 0072).
/// The numbers are the canvas students (Eilidh on track, Callum running short). The maths follows
/// PENNY_V3_BUILD.md B2 in whole pence, so the detailed breakdown adds up exactly.
/// The text is English, the way the server sends it for `language=en`.
enum ForecastMock {
    struct Account { var name: String; var kind: String; var pence: Int }
    struct Bill { var name: String; var short: String; var kind: String; var pence: Int; var due: String }
    struct NextMoney { var label: String; var short: String; var pence: Int; var date: String; var source: String; var url: String? }
    struct Week { var start: String; var end: String; var pence: Int }
    struct Income { var label: String; var pence: Int; var date: String; var source: String }

    struct Persona {
        var today: String
        var accounts: [Account]
        var bills: [Bill]
        var nextMoney: NextMoney
        /// The last 4 weeks of non-rent, non-bill spending.
        var weeks: [Week]
        /// Biggest non-rent category: (category, label, weekly pence).
        var biggest: (category: String, label: String, weeklyPence: Int)
        /// Smaller incomes due before the next money (added to money available).
        var expected: [Income] = []
    }

    /// Eilidh, University of Edinburgh: on track (canvas 1, 3, 3b).
    static let onTrack = Persona(
        today: "2026-10-18",
        accounts: [
            .init(name: "Santander current account", kind: "current", pence: 31_840),
            .init(name: "Savings pot", kind: "savings", pence: 30_000),
        ],
        bills: [
            .init(name: "Phone · EE", short: "Phone", kind: "bill", pence: 1_200, due: "2026-10-24"),
            .init(name: "Spotify Student", short: "Spotify", kind: "subscription", pence: 599, due: "2026-10-28"),
        ],
        nextMoney: .init(
            label: "SAAS loan", short: "Loan", pence: 73_500, date: "2026-11-02",
            source: "Your statement, matched to the SAAS payment dates (gov.uk)", url: "https://www.saas.gov.uk"
        ),
        weeks: [
            .init(start: "2026-09-20", end: "2026-09-26", pence: 13_100),
            .init(start: "2026-09-27", end: "2026-10-03", pence: 11_800),
            .init(start: "2026-10-04", end: "2026-10-10", pence: 12_600),
            .init(start: "2026-10-11", end: "2026-10-17", pence: 11_300),
        ],
        biggest: ("groceries", "Groceries", 2_600)
    )

    /// Callum, University of Leeds: running short (canvas 2).
    static let short = Persona(
        today: "2026-10-18",
        accounts: [.init(name: "Barclays current account", kind: "current", pence: 20_778)],
        bills: [
            .init(name: "Phone · Three", short: "Phone", kind: "bill", pence: 1_800, due: "2026-10-21"),
            .init(name: "PureGym", short: "Gym", kind: "subscription", pence: 1_200, due: "2026-10-21"),
        ],
        nextMoney: .init(label: "Pay from the bar job", short: "Pay", pence: 41_000, date: "2026-11-02", source: "Your statement", url: nil),
        weeks: [
            .init(start: "2026-09-20", end: "2026-09-26", pence: 12_100),
            .init(start: "2026-09-27", end: "2026-10-03", pence: 11_500),
            .init(start: "2026-10-04", end: "2026-10-10", pence: 12_000),
            .init(start: "2026-10-11", end: "2026-10-17", pence: 11_600),
        ],
        biggest: ("eating_out", "Eating out", 5_200)
    )

    /// Eilidh with her loan due in 10 days: fewer than 14 days left, so the total until the date shows.
    static var soon: Persona {
        var persona = onTrack
        persona.nextMoney.date = "2026-10-28"
        persona.bills = [persona.bills[0]]
        return persona
    }

    /// Callum overdrawn: bills and buffer are more than his money, so there is nothing to spend.
    static var overdrawn: Persona {
        var persona = short
        persona.accounts = [.init(name: "Barclays overdraft", kind: "overdraft", pence: -2_000)]
        return persona
    }

    /// ONS CPI annual rate for 2022 used by the stress test.
    static let inflation2022 = 9.1

    // MARK: Forecast

    static func forecast(_ persona: Persona, bufferPct: Int = 10, stress: Int? = nil) -> Forecast {
        let today = persona.today
        let moneyNow = persona.accounts.filter { $0.kind == "current" || $0.kind == "overdraft" }.reduce(0) { $0 + $1.pence }
        let billsTotal = persona.bills.reduce(0) { $0 + $1.pence }
        let expectedTotal = persona.expected.reduce(0) { $0 + $1.pence }
        let left = moneyNow + expectedTotal - billsTotal
        let buffer = max(0, Int((Double(left) * Double(bufferPct) / 100).rounded()))
        let spend = max(0, left - buffer)
        let days = max(1, dayCount(from: today, to: persona.nextMoney.date) - 1)
        let perDay = Int((Double(spend) / Double(days)).rounded())
        let perWeek = Int((Double(spend) * 7 / Double(days)).rounded())
        /// Fewer than 14 days left: the screens show the total until the date, not a weekly figure.
        let untilNext = days < 14
        let short = max(0, -(left - buffer))
        let usualWeekly = Int((Double(persona.weeks.reduce(0) { $0 + $1.pence }) / Double(persona.weeks.count)).rounded())
        let usualDaily = Double(usualWeekly) / 7
        let onTrack = spend > 0 && usualWeekly <= perWeek
        let weeks = Double(days) / 7
        let spare = onTrack ? Int((Double(perWeek - usualWeekly) * weeks).rounded()) : nil
        let runOutDays = onTrack ? nil : max(0, Int((Double(max(0, left)) / usualDaily).rounded(.down)))
        let runOut = runOutDays.map { addDays($0, to: today) }
        let next = persona.nextMoney
        let bigWeekly = persona.biggest.weeklyPence

        var json: [String: Any] = [
            "meta": ["data_status": "mock", "source": "sample", "as_of": addDays(-1, to: today), "label": "Sample data"],
            "question": "Will my money last until my next money arrives?",
            "state": onTrack ? "on_track" : "running_short",
            "today": today,
            "headline": onTrack ? "You'll make it to \(long(next.date))"
                : spend == 0 ? "Your money won't cover your bills before \(long(next.date))"
                : "At this pace, you run out on \(long(runOut!))",
            "budget_line": spend == 0
                ? "You are \(whole(short)) short before \(long(next.date))"
                : untilNext
                ? "\(onTrack ? "You can spend" : "Keep it under") \(whole(spend)) until \(long(next.date)) (about \(whole(perDay)) a day)"
                : "\(onTrack ? "You can spend" : "Keep it under") \(whole(perWeek)) a week (about \(whole(perDay)) a day)",
            "budget_period": untilNext ? "until_next_money" : "week",
            "to_spend": pounds(spend),
            "habit_line": onTrack
                ? "You usually spend \(whole(usualWeekly)), so you'll have about \(whole(spare ?? 0)) spare."
                : "You usually spend \(whole(usualWeekly)). \(persona.biggest.label) is your biggest cost: \(whole(bigWeekly)) a week.",
            "next_money": [
                "label": next.label, "amount": pounds(next.pence), "date": next.date,
                "source": source(next.source, next.url),
            ],
            "money_now": pounds(moneyNow),
            "accounts": persona.accounts.map {
                ["name": $0.name, "kind": $0.kind, "balance": pounds($0.pence), "counted": $0.kind == "current" || $0.kind == "overdraft"]
            },
            "bills": persona.bills.map { ["name": $0.name, "kind": $0.kind, "amount": pounds($0.pence), "due_date": $0.due] },
            "bills_total": pounds(billsTotal),
            "expected_income": persona.expected.map {
                ["label": $0.label, "amount": pounds($0.pence), "date": $0.date, "source": source($0.source, nil)] as [String: Any]
            },
            "expected_income_total": pounds(expectedTotal),
            "buffer_pct": bufferPct,
            "buffer_amount": pounds(buffer),
            "days": days,
            "per_day": pounds(perDay),
            "per_week": pounds(perWeek),
            "usual_weekly": pounds(usualWeekly),
            "usual_daily": (usualDaily).rounded() / 100,
            "usual_weeks": persona.weeks.map { ["start": $0.start, "end": $0.end, "amount": pounds($0.pence)] },
            "cpi_adjusted": false,
            "steps": [
                step("money_now", "Money now", moneyNow, "Your account today", ["Your statement"]),
                step("bills", "Bills before \(shortDate(next.date))", billsTotal,
                     persona.bills.map { "\($0.short) \(whole($0.pence))" }.joined(separator: ", "), ["Found in your statement"]),
                step("buffer", "Safety buffer, \(bufferPct)%", buffer,
                     "\(bufferPct)% of what's left after bills, kept back for surprises. 10% is recommended. You can change it.", []),
                step("result", "What you can spend", perWeek, "\(pence(spend)) over \(days) days", ["Your statement"]),
            ],
            "timeline": timeline(persona, runOut: runOut),
            "sources": [source("Your statement", nil), source(next.source, next.url), source("Bank of England", "https://www.bankofengland.co.uk")],
        ]
        if let spare { json["spare"] = pounds(spare) }
        if let runOut { json["run_out_date"] = runOut }
        if onTrack, let spare, spare > 1_000 {
            json["suggestion"] = [
                "kind": "save_spare", "text": "Put your \(whole(spare)) spare aside on \(long(next.date))", "amount": pounds(spare),
                "rate_pct": 3.5, "source": source("Bank of England", "https://www.bankofengland.co.uk"),
            ]
        } else if !onTrack {
            json["suggestion"] = [
                "kind": "cut_category", "text": "\(persona.biggest.label) is your biggest cost: \(whole(bigWeekly)) a week",
                "amount": pounds(bigWeekly), "category": persona.biggest.category, "source": source("Your statement", nil),
            ]
        }
        if stress == 2022 {
            let stressed = Int((Double(usualWeekly) * (1 + inflation2022 / 100)).rounded())
            let stillOK = stressed <= perWeek
            let stressRunOut = stillOK ? nil : addDays(Int((Double(left) / (Double(stressed) / 7)).rounded(.down)), to: today)
            var stressJSON: [String: Any] = [
                "year": 2022, "inflation_pct": inflation2022, "state": stillOK ? "on_track" : "running_short",
                "per_week": pounds(perWeek), "usual_weekly": pounds(stressed),
                "text": stillOK
                    ? "If prices rose \(inflation2022)% like in 2022, your usual \(whole(usualWeekly)) a week becomes \(whole(stressed)). You still make it to \(long(next.date))."
                    : "If prices rose \(inflation2022)% like in 2022, your usual \(whole(usualWeekly)) a week becomes \(whole(stressed)). You would run out on \(long(stressRunOut!)).",
                "source": source("ONS CPI, 2022", "https://www.ons.gov.uk/economy/inflationandpriceindices"),
            ]
            if let stressRunOut { stressJSON["run_out_date"] = stressRunOut }
            json["stress"] = stressJSON
        }
        return decode(json)
    }

    private static func timeline(_ persona: Persona, runOut: String?) -> [[String: Any]] {
        var points: [[String: Any]] = [["date": persona.today, "kind": "today", "label": "Today"]]
        // Bills on the same day merge into one point, as the engine does.
        var byDay: [(date: String, pence: Int, label: String)] = []
        for bill in persona.bills {
            if let index = byDay.firstIndex(where: { $0.date == bill.due }) {
                byDay[index].pence += bill.pence
                byDay[index].label = "Bills"
            } else {
                byDay.append((bill.due, bill.pence, bill.short))
            }
        }
        points += byDay.map { ["date": $0.date, "kind": "bill", "label": $0.label, "amount": pounds($0.pence)] }
        if let runOut { points.append(["date": runOut, "kind": "run_out", "label": "Runs out"]) }
        points.append(["date": persona.nextMoney.date, "kind": "next_money", "label": persona.nextMoney.short, "amount": pounds(persona.nextMoney.pence)])
        return points.sorted { ($0["date"] as! String) < ($1["date"] as! String) }
    }

    private static func step(_ id: String, _ title: String, _ amount: Int, _ text: String, _ sources: [String]) -> [String: Any] {
        ["id": id, "title": title, "amount": pounds(amount), "text": text, "sources": sources.map { source($0, nil) }]
    }

    private static func source(_ label: String, _ url: String?) -> [String: Any] {
        var value: [String: Any] = ["label": label]
        if let url { value["url"] = url }
        return value
    }

    // MARK: Spending months and categories

    /// `base` with `months` (4 statement months ending at its month). Another month gives a steady variant
    /// of `base`: same categories, amounts moved a little, shares and total recomputed.
    static func spending(base: SpendingResponse, month: String?) -> SpendingResponse {
        let months = (0..<4).reversed().map { addMonths(-$0, to: base.month) }
        var response = base
        if response.months == nil || response.months?.isEmpty == true { response.months = months }
        guard let month, month != base.month, let position = months.lastIndex(of: month) else { return response }
        let offset = months.count - 1 - position
        response.month = month
        response.meta.asOf = lastDay(of: month)
        let amounts = base.categories.enumerated().map { index, category in
            category.category.rawValue == "housing" ? category.amount : variant(category.amount, index: index, offset: offset)
        }
        let total = amounts.reduce(0, +)
        response.total = (total * 100).rounded() / 100
        response.categories = zip(base.categories, amounts).enumerated().map { index, pair in
            var category = pair.0
            category.amount = pair.1
            category.share = total > 0 ? ((pair.1 / total) * 1_000).rounded() / 1_000 : 0
            category.transactions = max(category.transactions - offset % 2, pair.1 > 0 ? 1 : 0)
            if offset < 3 {
                let previous = category.category.rawValue == "housing" ? pair.1 : variant(base.categories[index].amount, index: index, offset: offset + 1)
                category.changePct = previous > 0 ? ((pair.1 / previous - 1) * 1_000).rounded() / 10 : nil
            } else {
                category.changePct = nil
            }
            return category
        }
        return response
    }

    private static func variant(_ amount: Double, index: Int, offset: Int) -> Double {
        let factor = 1 + 0.12 * sin(Double(index * 3 + offset * 5))
        return ((amount * factor) * 100).rounded() / 100
    }

    private static let merchants: [String: [String]] = [
        "groceries": ["Tesco Express", "Lidl", "Sainsbury's Local", "Aldi", "Co-op"],
        "eating_out": ["Greggs", "Nando's", "Pret A Manger", "Domino's", "Uni café"],
        "transport": ["Lothian Buses", "Trainline", "Uber", "Stagecoach"],
        "shopping": ["Primark", "Amazon", "Boots", "TK Maxx"],
        "entertainment": ["Odeon", "Students' Union bar", "Ticketmaster"],
        "housing": ["Rent"],
        "bills": ["EE", "Octopus Energy"],
        "subscriptions": ["Spotify", "Netflix"],
    ]

    /// One category in one month: total and transactions from `spending`, weekly bars from the transactions.
    static func categoryDetail(spending: SpendingResponse, category: String) -> CategoryDetail? {
        guard let spend = spending.categories.first(where: { $0.category.rawValue == category }) else { return nil }
        let totalPence = Int((spend.amount * 100).rounded())
        let count = max(1, spend.transactions)
        // Weights 1.0, 1.4, 0.7, 1.2, 0.9, ... give a steady, uneven split. The last part takes the remainder.
        let weights = (0..<count).map { 1 + 0.35 * sin(Double($0 * 2 + 1)) }
        let weightSum = weights.reduce(0, +)
        var parts = weights.map { Int((Double(totalPence) * $0 / weightSum).rounded(.down)) }
        parts[count - 1] += totalPence - parts.reduce(0, +)
        let lastDayNumber = Int(spending.meta.asOf.prefix(10).suffix(2)).flatMap { $0 > 0 ? $0 : nil } ?? 28
        let names = merchants[category] ?? [spend.label]
        var transactions: [[String: Any]] = []
        for (index, part) in parts.enumerated() {
            let day = max(1, lastDayNumber - (index * max(1, lastDayNumber - 1)) / max(1, count))
            let date = spending.month + "-" + String(format: "%02d", day)
            let name = names[index % names.count]
            transactions.append([
                "id": "tx_\(category)_\(index)", "account_id": "acc_1", "date": date, "amount": -pounds(part),
                "currency": "GBP", "description": name.uppercased(), "merchant": name,
            ])
        }
        var weeks: [[String: Any]] = []
        var start = 1
        while start <= lastDayNumber {
            let end = min(start + 6, lastDayNumber)
            let sum = zip(transactions, parts).reduce(0) { total, pair in
                let day = Int((pair.0["date"] as! String).suffix(2))!
                return (start...end).contains(day) ? total + pair.1 : total
            }
            weeks.append([
                "start": spending.month + "-" + String(format: "%02d", start),
                "end": spending.month + "-" + String(format: "%02d", end), "amount": pounds(sum),
            ])
            start += 7
        }
        let usual = spend.changePct.map { spend.amount / (1 + $0 / 100) } ?? spend.amount
        let json: [String: Any] = [
            "meta": ["data_status": spending.meta.dataStatus.rawValue, "source": spending.meta.source, "as_of": spending.meta.asOf],
            "category": category, "label": spend.label, "month": spending.month, "total": pounds(totalPence),
            "usual_monthly": (usual * 100).rounded() / 100, "weeks": weeks, "transactions": transactions,
        ]
        return decode(json)
    }

    // MARK: Helpers

    static func pounds(_ pence: Int) -> Double { Double(pence) / 100 }

    private static func whole(_ pence: Int) -> String { Money.format((Double(pence) / 100).rounded()) }
    private static func pence(_ pence: Int) -> String { FinanceMapping.pounds(Double(pence) / 100) }

    private static let utc: Calendar = {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "UTC")!
        return calendar
    }()

    private static func formatter(_ format: String) -> DateFormatter {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_GB")
        formatter.timeZone = TimeZone(identifier: "UTC")
        formatter.dateFormat = format
        return formatter
    }

    static func dayCount(from: String, to: String) -> Int {
        guard let a = FinanceMapping.date(from), let b = FinanceMapping.date(to) else { return 0 }
        return utc.dateComponents([.day], from: a, to: b).day ?? 0
    }

    static func addDays(_ days: Int, to raw: String) -> String {
        guard let date = FinanceMapping.date(raw), let moved = utc.date(byAdding: .day, value: days, to: date) else { return raw }
        return formatter("yyyy-MM-dd").string(from: moved)
    }

    static func addMonths(_ months: Int, to month: String) -> String {
        guard let date = FinanceMapping.date(month + "-01"), let moved = utc.date(byAdding: .month, value: months, to: date) else { return month }
        return formatter("yyyy-MM").string(from: moved)
    }

    private static func lastDay(of month: String) -> String {
        addDays(-1, to: addMonths(1, to: month) + "-01")
    }

    private static func long(_ raw: String) -> String {
        FinanceMapping.date(raw).map { formatter("d MMMM").string(from: $0) } ?? raw
    }

    private static func shortDate(_ raw: String) -> String {
        FinanceMapping.date(raw).map { formatter("d MMM").string(from: $0) } ?? raw
    }

    private static func decode<T: Decodable>(_ json: [String: Any]) -> T {
        do {
            let data = try JSONSerialization.data(withJSONObject: json)
            return try ContractExamples.decoder.decode(T.self, from: data)
        } catch {
            fatalError("ForecastMock cannot build \(T.self): \(error)")
        }
    }
}
