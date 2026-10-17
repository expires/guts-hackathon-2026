import Foundation

/// Presentation mode (ADR 0029, milestone 4) for ViewModel text in W7 screens.
/// Money follows DesignSystem `LLAmountFormat`: under £1,000 to the nearest £10, else the nearest £100,
/// never pence. Personal names, account numbers and merchant names become generic words.
enum PresentationFormat {
    /// "£12,500" (off) or "£12,500" rounded (on).
    static func money(_ value: Double, _ presentation: Bool, style: LLAmountStyle = .standard) -> String {
        LLAmountFormat(style: style, presentation: presentation).format(value)
    }

    /// A person's name, or "You" in presentation mode.
    static func name(_ name: String, _ presentation: Bool, generic: String = "You") -> String {
        presentation ? generic : name
    }

    /// A merchant, or "A shop" in presentation mode.
    static func merchant(_ name: String, _ presentation: Bool) -> String {
        presentation ? "A shop" : name
    }

    /// A bank or provider name, or "Your bank" in presentation mode.
    static func bank(_ name: String, _ presentation: Bool) -> String {
        presentation ? "Your bank" : name
    }

    // "£1,234.56", "-£16", "£950". The sign before £ is kept.
    private static let amountPattern = try? NSRegularExpression(pattern: #"(-?)£(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"#)
    // 8 or more digits in a row (account numbers) and sort codes ("12-34-56").
    private static let accountPattern = try? NSRegularExpression(pattern: #"\b\d{2}-\d{2}-\d{2}\b|\b\d{8,}\b"#)

    /// Rounds every pound amount and hides account numbers and sort codes in server-written text
    /// (headlines, evidence, personal facts). Off: the text as written.
    static func text(_ text: String, _ presentation: Bool) -> String {
        guard presentation else { return text }
        var result = text
        if let accountPattern {
            result = accountPattern.stringByReplacingMatches(
                in: result, range: NSRange(result.startIndex..., in: result), withTemplate: "••••"
            )
        }
        guard let amountPattern else { return result }
        let matches = amountPattern.matches(in: result, range: NSRange(result.startIndex..., in: result))
        for match in matches.reversed() {
            guard let whole = Range(match.range, in: result),
                  let digits = Range(match.range(at: 2), in: result),
                  let value = Double(result[digits].replacingOccurrences(of: ",", with: "")) else { continue }
            let negative = match.range(at: 1).length > 0
            result.replaceSubrange(whole, with: money(negative ? -value : value, true))
        }
        return result
    }
}
