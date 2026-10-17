import Foundation

/// Shared mapping for Money tab responses (ADR 0016, 0017, 0018).
enum FinanceMapping {
    /// True when the response is labelled sample data (`meta.data_status == mock`).
    static func isSample(_ meta: FinanceMeta) -> Bool {
        meta.dataStatus == .mock
    }

    /// Parses "YYYY-MM-DD" in UTC.
    static func date(_ raw: String) -> Date? {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.timeZone = TimeZone(identifier: "UTC")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter.date(from: String(raw.prefix(10)))
    }

    /// "31 Mar 2027". Returns the raw text when it does not parse.
    static func dayText(_ raw: String) -> String {
        guard let date = date(raw) else { return raw }
        return format(date, template: "dMMMyyyy")
    }

    /// "Fri 17 Oct".
    static func shortDayText(_ raw: String) -> String {
        guard let date = date(raw) else { return raw }
        return format(date, template: "EEEdMMM")
    }

    /// "October 2026" from "2026-10".
    static func monthText(_ raw: String) -> String {
        guard let date = date(raw + "-01") else { return raw }
        return format(date, template: "MMMMyyyy")
    }

    /// Formats a UTC date with an en_GB template, so text does not change with the device region.
    static func format(_ date: Date, template: String) -> String {
        let formatter = DateFormatter()
        formatter.locale = Money.locale
        formatter.timeZone = TimeZone(identifier: "UTC")
        formatter.setLocalizedDateFormatFromTemplate(template)
        return formatter.string(from: date)
    }

    /// "£12.99" with pence, for small amounts such as subscriptions and daily spend.
    static func pounds(_ value: Double) -> String {
        value.formatted(.currency(code: "GBP").locale(Money.locale).precision(.fractionLength(2)))
    }

    /// "69%" from 0.69.
    static func percent(_ share: Double) -> String {
        (share * 100).rounded().formatted(.number.precision(.fractionLength(0))) + "%"
    }

    /// Chart points from contract points. x is days since the first point.
    static func chartPoints(_ points: [Components.Schemas.Point]) -> [ChartState.Point] {
        let first = points.first.flatMap { date($0.date) }
        return points.enumerated().map { offset, point in
            let x = first.flatMap { start in date(point.date).map { $0.timeIntervalSince(start) / 86_400 } } ?? Double(offset)
            return ChartState.Point(x: x, y: point.value, label: dayText(point.date))
        }
    }
}
