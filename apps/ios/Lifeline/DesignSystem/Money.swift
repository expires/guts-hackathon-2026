import Foundation

/// Money formatting. Always GBP with the en_GB locale, so text does not change with the device region.
enum Money {
    static let locale = Locale(identifier: "en_GB")

    /// "£12,500" or "-£11,000". Whole pounds.
    static func format(_ value: Double) -> String {
        value.formatted(
            .currency(code: "GBP")
                .locale(locale)
                .precision(.fractionLength(0))
        )
    }

    /// "+£600" or "-£540". Zero is "£0".
    static func signed(_ value: Double) -> String {
        let rounded = value.rounded()
        if rounded > 0 { return "+" + format(rounded) }
        return format(rounded)
    }

    /// Short form for tight spaces: "£950", "£12.5k", "-£1.2m".
    static func compact(_ value: Double) -> String {
        let magnitude = abs(value)
        let sign = value < 0 ? "-" : ""
        switch magnitude {
        case ..<1_000:
            return sign + "£" + String(Int(magnitude.rounded()))
        case ..<1_000_000:
            return sign + "£" + trimmed(magnitude / 1_000) + "k"
        default:
            return sign + "£" + trimmed(magnitude / 1_000_000) + "m"
        }
    }

    /// Spoken form for VoiceOver: "minus 11,000 pounds".
    static func spoken(_ value: Double) -> String {
        let number = abs(value.rounded()).formatted(.number.locale(locale).precision(.fractionLength(0)))
        return (value < 0 ? "minus " : "") + number + " pounds"
    }

    private static func trimmed(_ value: Double) -> String {
        let oneDecimal = (value * 10).rounded() / 10
        if oneDecimal == oneDecimal.rounded() {
            return String(Int(oneDecimal))
        }
        return String(format: "%.1f", oneDecimal)
    }
}
