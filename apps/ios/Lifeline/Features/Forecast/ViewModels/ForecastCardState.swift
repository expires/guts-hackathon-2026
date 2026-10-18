import Foundation

extension Components.Schemas.Forecast {
    /// `next_money`, nil in the no_next_money state. Works whether the generated field is optional or not.
    var nextMoneyIfAny: Components.Schemas.NextMoney? { nextMoney }
    /// Smaller incomes due before the next money (weekly pay, family). Added to money available.
    var incomeExpected: [Components.Schemas.ForecastIncome] { expectedIncome ?? [] }
    var incomeExpectedTotal: Double { expectedIncomeTotal ?? 0 }
    /// Money now plus expected income: everything there is to cover the days until the next money.
    var moneyAvailable: Double { moneyNow + incomeExpectedTotal }
    /// Fewer than 14 days to the next money: screens show the total until the date, not a weekly figure.
    var isUntilNextMoney: Bool { budgetPeriod == .untilNextMoney }
    /// Money to spend until the next money (`to_spend`), else money available − bills − buffer.
    var moneyToSpend: Double {
        if let toSpend, toSpend > 0 { return toSpend }
        return max(0, moneyAvailable - billsTotal - bufferAmount)
    }
    /// Running short with nothing to spend at all (e.g. overdrawn): the card shows the server's budget line.
    var hasNothingToSpend: Bool { state == .runningShort && perDay <= 0 }
}

/// Text helpers for the forecast screens (ADR 0072). Cards round to whole pounds; the breakdown shows pence.
enum ForecastText {
    /// "£135". Whole pounds.
    static func whole(_ value: Double) -> String { Money.format(value.rounded()) }
    /// "£318.40".
    static func pence(_ value: Double) -> String { FinanceMapping.pounds(value) }
    /// "−£17.99": a true minus sign for money taken away.
    static func minusPence(_ value: Double) -> String { "\u{2212}" + pence(abs(value)) }
    /// "−£18".
    static func minusWhole(_ value: Double) -> String { "\u{2212}" + whole(abs(value)) }
    /// Whole pence, so sums compare exactly.
    static func toPence(_ value: Double) -> Int { Int((value * 100).rounded()) }
    /// "2 November".
    static func longDate(_ raw: String) -> String {
        FinanceMapping.date(raw).map { FinanceMapping.format($0, template: "dMMMM") } ?? raw
    }
    /// "24 Oct".
    static func shortDate(_ raw: String) -> String { FinanceMapping.shortDateText(raw) }
    /// "Oct".
    static func shortMonth(_ month: String) -> String { FinanceMapping.shortMonthText(month + "-01") }
    /// "October".
    static func monthName(_ month: String) -> String {
        FinanceMapping.date(month + "-01").map { FinanceMapping.format($0, template: "MMMM") } ?? month
    }

    /// B4: the only sources a student sees. Any other label (Land Registry, mock, cut banks) is dropped.
    static let allowedSources = [
        "statement", "gov.uk", "saas", "student finance", "bank of england", "ons", "nomis", "octopus", "frankfurter", "mpc",
    ]

    /// The label when it is an allowed student-facing source, else nil.
    static func source(_ label: String) -> String? {
        let lower = label.lowercased()
        if lower.contains("mock") || lower.contains("sample") || lower.contains("land registry") { return nil }
        return allowedSources.contains { lower.contains($0) } ? label : nil
    }

    /// Allowed labels only, in order, without repeats.
    static func sources(_ list: [Components.Schemas.ForecastSource]?) -> [String] {
        var seen = Set<String>()
        return (list ?? []).compactMap { source($0.label) }.filter { seen.insert($0).inserted }
    }

    static func days(from: String, to: String) -> Int { ForecastMock.dayCount(from: from, to: to) }
    static func addDays(_ days: Int, to raw: String) -> String { ForecastMock.addDays(days, to: raw) }

    /// "2 weeks" or "2.4 weeks".
    static func weeks(_ days: Int) -> String {
        let weeks = Double(days) / 7
        if days % 7 == 0 { return days == 7 ? L10n.tr("1 week") : L10n.tr("\(days / 7) weeks") }
        let text = weeks.formatted(.number.precision(.fractionLength(1)).locale(Locale(identifier: "en_GB")))
        return L10n.tr("\(text) weeks")
    }
}

/// The forecast card at the top of Money home (B3.1, canvas 1 and 2).
struct ForecastCardState: Equatable, Sendable {
    enum Status: Equatable, Sendable { case onTrack, runningShort, noNextMoney }

    struct Point: Equatable, Sendable, Identifiable {
        enum Kind: Equatable, Sendable { case today, bill, nextMoney, runOut }
        var id: Int
        var kind: Kind
        /// "Today", "Phone £12", "Runs out", "Loan £735".
        var title: String
        /// "18 Oct".
        var dateText: String
    }

    var status: Status
    /// "On track", "Running short", "No money due yet".
    var chipText: String
    /// From the server: "You'll make it to 2 November".
    var headline: String
    /// "Your next money: SAAS loan, £735." or "That's 5 days before your next money on 2 November."
    var subline: String?
    /// "You can spend" or "Keep it under". Nil without a weekly figure.
    var budgetLead: String?
    /// "£135" (rounded `per_week`), or the total until the next money when fewer than 14 days are left.
    var weeklyAmount: String?
    /// "a week" or "until 28 Oct".
    var unitText: String = L10n.tr("a week")
    /// Nothing to spend: the server's line, "You are £50 short before 2 November".
    var budgetNote: String?
    /// "(about £19 a day)". Rounded from `per_day`.
    var dailyText: String?
    /// "You usually spend £122, so you'll have about £26 spare."
    var habitLine: String?
    /// Today, bills, run-out day and next money in date order. At most 5 points.
    var timeline: [Point]

    /// One sentence for VoiceOver.
    var accessibilitySummary: String {
        [chipText, headline, subline, budgetNote, [budgetLead, weeklyAmount, weeklyAmount == nil ? nil : unitText, dailyText].compactMap { $0 }.joined(separator: " "), habitLine]
            .compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: ". ")
    }

    static func make(_ forecast: Forecast) -> ForecastCardState {
        let status: Status = switch forecast.state {
        case .onTrack: .onTrack
        case .runningShort: .runningShort
        case .noNextMoney: .noNextMoney
        }
        let next = forecast.nextMoneyIfAny
        let subline: String? = switch status {
        case .onTrack:
            next.map { L10n.tr("Your next money: \($0.label), \(ForecastText.whole($0.amount)).") }
        case .runningShort:
            forecast.runOutDate.flatMap { runOut in next.map { next in
                let gap = ForecastText.days(from: runOut, to: next.date)
                let date = ForecastText.longDate(next.date)
                return gap == 1
                    ? L10n.tr("That's 1 day before your next money on \(date).")
                    : L10n.tr("That's \(gap) days before your next money on \(date).")
            } }
        case .noNextMoney:
            L10n.tr("Penny found no money coming in yet.")
        }
        let hasBudget = status != .noNextMoney && next != nil && forecast.days > 0 && !forecast.hasNothingToSpend
        let until = forecast.isUntilNextMoney
        let chipText: String = switch status {
        case .onTrack: L10n.tr("On track")
        case .runningShort: L10n.tr("Running short")
        case .noNextMoney: L10n.tr("No money due yet")
        }
        return ForecastCardState(
            status: status,
            chipText: chipText,
            headline: forecast.headline,
            subline: subline,
            budgetLead: hasBudget ? (status == .onTrack ? L10n.tr("You can spend") : L10n.tr("Keep it under")) : nil,
            weeklyAmount: hasBudget ? ForecastText.whole(until ? forecast.moneyToSpend : max(0, forecast.perWeek)) : nil,
            unitText: until ? L10n.tr("until \(next.map { ForecastText.shortDate($0.date) } ?? "")") : L10n.tr("a week"),
            budgetNote: forecast.hasNothingToSpend ? forecast.budgetLine : nil,
            dailyText: hasBudget ? L10n.tr("(about \(ForecastText.whole(max(0, forecast.perDay))) a day)") : nil,
            habitLine: forecast.habitLine.flatMap { $0.isEmpty ? nil : $0 } ?? habitLine(forecast),
            timeline: status == .noNextMoney ? [] : timeline(forecast)
        )
    }

    /// Fallback when the server sends no habit line.
    static func habitLine(_ forecast: Forecast) -> String? {
        guard forecast.usualWeekly > 0 else { return nil }
        return L10n.tr("You usually spend \(ForecastText.whole(forecast.usualWeekly)) a week.")
    }

    /// Today first, next money last. Bills fill the middle; more than fit merge into one "Bills £X" point.
    static func timeline(_ forecast: Forecast) -> [Point] {
        var bills = forecast.timeline.filter { $0.kind == .bill }
        let runOut = forecast.timeline.first { $0.kind == .runOut }
        let slots = runOut == nil ? 3 : 2
        if bills.count > slots {
            let kept = Array(bills.prefix(slots - 1))
            let rest = bills.dropFirst(slots - 1)
            var merged = rest.first!
            merged.label = L10n.tr("Bills")
            merged.amount = rest.compactMap(\.amount).reduce(0, +)
            bills = kept + [merged]
        }
        var points: [Components.Schemas.TimelinePoint] = []
        if let today = forecast.timeline.first(where: { $0.kind == .today }) { points.append(today) }
        points += bills
        if let runOut { points.append(runOut) }
        if let next = forecast.timeline.first(where: { $0.kind == .nextMoney }) { points.append(next) }
        let sorted = points.enumerated().sorted { lhs, rhs in
            // Today stays first and next money last, even on the same day as a bill.
            func rank(_ point: Components.Schemas.TimelinePoint) -> Int {
                switch point.kind { case .today: 0; case .bill: 1; case .runOut: 2; case .nextMoney: 3 }
            }
            return (lhs.element.date, rank(lhs.element), lhs.offset) < (rhs.element.date, rank(rhs.element), rhs.offset)
        }
        return sorted.enumerated().map { index, pair in
            let point = pair.element
            let kind: Point.Kind = switch point.kind {
            case .today: .today
            case .bill: .bill
            case .nextMoney: .nextMoney
            case .runOut: .runOut
            }
            let title: String = switch kind {
            case .today: L10n.tr("Today")
            case .runOut: L10n.tr("Runs out")
            case .bill, .nextMoney: point.amount.map { "\(point.label) \(ForecastText.whole($0))" } ?? point.label
            }
            return Point(id: index, kind: kind, title: title, dateText: ForecastText.shortDate(point.date))
        }
    }
}

/// "Due before 2 November": the bills in the forecast window (B3.2).
struct ForecastDueState: Equatable, Sendable {
    struct Row: Equatable, Sendable, Identifiable {
        var id: Int
        var name: String
        var dateText: String
        var amountText: String
    }

    /// "Due before 2 November".
    var title: String
    /// "£18".
    var totalText: String
    var rows: [Row]

    static func make(_ forecast: Forecast) -> ForecastDueState? {
        guard forecast.state != .noNextMoney, let next = forecast.nextMoneyIfAny else { return nil }
        let date = ForecastText.longDate(next.date)
        return ForecastDueState(
            title: L10n.tr("Due before \(date)"),
            totalText: ForecastText.whole(forecast.billsTotal),
            rows: forecast.bills.sorted { $0.dueDate < $1.dueDate }.enumerated().map { index, bill in
                Row(id: index, name: bill.name, dateText: ForecastText.shortDate(bill.dueDate), amountText: ForecastText.whole(bill.amount))
            }
        )
    }
}

/// "One thing that helps": the forecast's one suggestion (B2, B3.2).
struct ForecastHelpState: Equatable, Sendable {
    enum Kind: Equatable, Sendable { case save, cut }
    var kind: Kind
    /// From the server: "Put your £26 spare aside on 2 November".
    var title: String
    /// "Easy-access savings pay about 3.5% a year. Source: Bank of England."
    var detail: String?

    static func make(_ forecast: Forecast) -> ForecastHelpState? {
        guard let suggestion = forecast.suggestion else { return nil }
        switch suggestion.kind {
        case .saveSpare:
            let rate = suggestion.ratePct.map { $0.formatted(.number.precision(.fractionLength(0...2)).locale(Locale(identifier: "en_GB"))) }
            let source = suggestion.source.flatMap { ForecastText.source($0.label) } ?? "Bank of England"
            return .init(kind: .save, title: suggestion.text, detail: rate.map { L10n.tr("Easy-access savings pay about \($0)% a year. Source: \(source).") })
        case .cutCategory:
            return .init(
                kind: .cut, title: suggestion.text,
                detail: L10n.tr("Your biggest cost after rent and bills. Spending less here helps most.")
            )
        }
    }
}
