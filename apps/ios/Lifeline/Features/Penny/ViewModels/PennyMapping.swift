import Foundation

/// Pure mapping from chat contract types to `PennyViewState` parts. Used by the ViewModel, fixtures and tests.
enum PennyMapping {
    static let checkedLabel = "Checked with your data"
    static let generalLabel = "General answer"
    static let officialLabel = "Checked against official sources"
    /// ADR 0051. Replaces "Not financial advice".
    static let disclaimer = "Penny is AI and can make mistakes. Guidance only, not regulated financial advice. Check before big decisions."
    /// Chat failure text (DIRECTION_V2 section 6, fix 9).
    static let unavailable = "Penny is unavailable right now. Try again."

    /// Units that may be highlighted: money and rates only, never years, dates, counts or months.
    static func isHighlightable(_ unit: String) -> Bool {
        unit.hasPrefix("gbp") || unit == "percent"
    }

    /// Shown in presentation mode for a pound amount that cannot be read as a number.
    static let maskedAmount = "£•••"

    /// Presentation mode (DesignSystem `LLAmountFormat`): under £1,000 to the nearest £10, else the nearest £100.
    static func presentationMoney(_ value: Double) -> String {
        LLAmountFormat(style: .standard, presentation: true).format(value)
    }

    /// Rounds a streamed amount such as "£1,050" or "-£16" before its fact arrives. Nil when it is not one amount.
    static func roundedAmountText(_ text: String) -> String? {
        let trimmed = text.trimmingCharacters(in: .whitespaces)
        guard trimmed.contains("£") else { return nil }
        let negative = trimmed.hasPrefix("-")
        let digits = trimmed.replacingOccurrences(of: "£", with: "").replacingOccurrences(of: ",", with: "")
            .replacingOccurrences(of: "-", with: "")
        guard let value = Double(digits) else { return nil }
        return presentationMoney(negative ? -value : value)
    }

    // MARK: Highlights

    /// A highlight that fits inside its bubble's text, in Unicode scalar offsets (the API counts Python
    /// string indices, which are code points).
    struct Span: Equatable, Sendable {
        var start: Int
        var length: Int
        var factID: String
        var sourceID: String?
    }

    /// Valid spans for one bubble, sorted. Spans out of range, empty or overlapping an earlier span are dropped.
    static func spans(for bubbleID: String, text: String, highlights: [PennyAPI.Highlight]) -> [Span] {
        let count = text.unicodeScalars.count
        var result: [Span] = []
        for h in highlights.filter({ $0.bubbleId == bubbleID }).sorted(by: { $0.start < $1.start }) {
            guard h.start >= 0, h.length > 0, h.start + h.length <= count else { continue }
            if let last = result.last, h.start < last.start + last.length { continue }
            result.append(Span(start: h.start, length: h.length, factID: h.factId, sourceID: h.sourceId))
        }
        return result
    }

    /// Splits text into plain and highlighted segments. `replacement` returns the text shown for a span
    /// (presentation mode masks money). Highlight ids are "<prefix>.<index>".
    static func segments(
        text: String,
        spans: [Span],
        idPrefix: String,
        replacement: (Span, String) -> String = { _, original in original }
    ) -> [PennyViewState.Segment] {
        let scalars = Array(text.unicodeScalars)
        var segments: [PennyViewState.Segment] = []
        var cursor = 0
        func piece(_ from: Int, _ to: Int) -> String {
            var view = String.UnicodeScalarView()
            view.append(contentsOf: scalars[from..<to])
            return String(view)
        }
        for (index, span) in spans.enumerated() {
            if span.start > cursor {
                segments.append(.init(id: segments.count, text: piece(cursor, span.start)))
            }
            let original = piece(span.start, span.start + span.length)
            segments.append(.init(id: segments.count, text: replacement(span, original), highlightID: "\(idPrefix).\(index)"))
            cursor = span.start + span.length
        }
        if cursor < scalars.count {
            segments.append(.init(id: segments.count, text: piece(cursor, scalars.count)))
        }
        return segments
    }

    // MARK: Values

    static func isMoney(_ unit: String) -> Bool { unit.hasPrefix("gbp") }

    /// "£1,050 a month", "4.98%", "4 months", "2027". Money is masked in presentation mode.
    static func valueText(value: Double, unit: String, presentation: Bool) -> String {
        let money = presentation ? presentationMoney(value) : Money.format(value)
        switch unit {
        case "gbp": return money
        case "gbp_per_month": return money + " a month"
        case "gbp_per_year": return money + " a year"
        case "percent":
            return value.formatted(.number.locale(Money.locale).precision(.fractionLength(0...2))) + "%"
        case "months": return plural(value, "month")
        case "years": return plural(value, "year")
        case "date_year": return String(Int(value.rounded()))
        default: return value.formatted(.number.locale(Money.locale).precision(.fractionLength(0...1)))
        }
    }

    private static func plural(_ value: Double, _ word: String) -> String {
        let number = value.formatted(.number.locale(Money.locale).precision(.fractionLength(0...1)))
        return "\(number) \(word)\(value == 1 ? "" : "s")"
    }

    // MARK: Time

    static func parseDate(_ iso: String?) -> Date? {
        guard let iso else { return nil }
        let plain = ISO8601DateFormatter()
        if let date = plain.date(from: iso) { return date }
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return fractional.date(from: iso)
    }

    /// "Updated just now", "Updated 5 min ago", "Updated 3 h ago", "Updated 2 days ago".
    static func updatedText(_ iso: String?, now: Date) -> String? {
        guard let date = parseDate(iso) else { return nil }
        let seconds = max(0, now.timeIntervalSince(date))
        switch seconds {
        case ..<60: return "Updated just now"
        case ..<3_600: return "Updated \(Int(seconds / 60)) min ago"
        case ..<86_400: return "Updated \(Int(seconds / 3_600)) h ago"
        default:
            let days = Int(seconds / 86_400)
            return "Updated \(days) day\(days == 1 ? "" : "s") ago"
        }
    }

    // MARK: Sources

    static let groupOrder: [(id: String, title: String)] = [
        ("your_data", "Your data"), ("live_sources", "Live sources"), ("general_knowledge", "General knowledge"),
    ]

    static func sourceGroups(_ sources: [PennyAPI.Source], now: Date) -> [PennyViewState.SourceGroup] {
        groupOrder.compactMap { group in
            let rows = sources.filter { $0.group.rawValue == group.id }.map { source in
                PennyViewState.SourceRow(
                    id: source.id,
                    label: source.label,
                    updatedText: updatedText(source.updatedAt, now: now),
                    status: source.ref.map { StateMapping.status($0.status.rawValue) },
                    url: source.url.flatMap(URL.init(string:))
                )
            }
            return rows.isEmpty ? nil : .init(id: group.id, title: group.title, rows: rows)
        }
    }

    /// Collapsed sources card title (DIRECTION_V2 section 6, fix 5).
    static func sourcesTitle(count: Int) -> String {
        "See sources"
    }

    /// "General answer" (no engine tool), "Checked with your data" (a source from your data), else
    /// "Checked against official sources" (facts table or official sources only).
    static func modeLabel(_ response: PennyAPI.Response) -> String {
        if isGeneral(response) { return generalLabel }
        let usesYourData = (response.sources ?? []).contains { $0.group.rawValue == "your_data" }
        return usesYourData ? checkedLabel : officialLabel
    }

    static func isGeneral(_ response: PennyAPI.Response) -> Bool {
        response.mode?.rawValue == "general"
    }

    // MARK: Bubbles and groups

    static func kind(_ raw: String) -> PennyViewState.Bubble.Kind {
        switch raw {
        case "caveat": .caveat
        case "question": .question
        case "general_knowledge": .generalKnowledge
        default: .answer
        }
    }

    /// One bubble plus the number cards for its highlights.
    static func bubble(
        _ bubble: PennyAPI.Bubble,
        highlights: [PennyAPI.Highlight],
        facts: [PennyAPI.Fact],
        sources: [PennyAPI.Source],
        groupID: String,
        presentation: Bool,
        now: Date
    ) -> (PennyViewState.Bubble, [String: PennyViewState.HighlightDetail]) {
        let factsByID = Dictionary(facts.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        let scalars = Array(bubble.text.unicodeScalars)
        let spans = spans(for: bubble.id, text: bubble.text, highlights: highlights).filter { span in
            if let fact = factsByID[span.factID] { return isHighlightable(fact.unit.rawValue) }
            // Streaming: facts arrive with `done`. Keep only spans that read as money or a rate.
            var view = String.UnicodeScalarView()
            view.append(contentsOf: scalars[span.start..<(span.start + span.length)])
            let text = String(view)
            return text.contains("£") || text.contains("%")
        }
        let prefix = "\(groupID).\(bubble.id)"
        let sourcesByID = Dictionary(sources.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
        let segments = segments(text: bubble.text, spans: spans, idPrefix: prefix) { span, original in
            guard presentation else { return original }
            guard let fact = factsByID[span.factID] else {
                // Streaming: facts arrive with `done`. Round a highlighted amount in pounds until then.
                guard original.contains("£") else { return original }
                return roundedAmountText(original) ?? maskedAmount
            }
            guard isMoney(fact.unit.rawValue) else { return original }
            // Keep the bubble's own wording ("£1,050" inside "costs £1,050 a month"): round the amount only.
            return roundedAmountText(original) ?? presentationMoney(fact.value)
        }
        var details: [String: PennyViewState.HighlightDetail] = [:]
        for (index, span) in spans.enumerated() {
            let id = "\(prefix).\(index)"
            let fact = factsByID[span.factID]
            let source = (span.sourceID ?? fact?.sourceId).flatMap { sourcesByID[$0] }
            let shown = segments.first { $0.highlightID == id }?.text ?? ""
            details[id] = .init(
                id: id,
                bubbleID: bubble.id,
                label: fact?.label ?? "Number",
                valueText: fact.map { valueText(value: $0.value, unit: $0.unit.rawValue, presentation: presentation) } ?? shown,
                sourceLabel: source?.label,
                updatedText: updatedText(source?.updatedAt, now: now),
                status: source?.ref.map { StateMapping.status($0.status.rawValue) }
            )
        }
        let state = PennyViewState.Bubble(
            id: bubble.id,
            kind: kind(bubble.kind.rawValue),
            segments: segments,
            text: segments.map(\.text).joined()
        )
        return (state, details)
    }

    /// A finished answer group from `done.response` or `POST /v1/chat`.
    static func answerGroup(
        _ response: PennyAPI.Response,
        presentation: Bool,
        now: Date,
        isComplete: Bool = true
    ) -> PennyViewState.AnswerGroup {
        let groupID = response.messageId
        var bubbles: [PennyViewState.Bubble] = []
        var details: [String: PennyViewState.HighlightDetail] = [:]
        for item in response.bubbles {
            let (bubble, cards) = bubble(
                item, highlights: response.highlights ?? [], facts: response.facts ?? [],
                sources: response.sources ?? [], groupID: groupID, presentation: presentation, now: now
            )
            bubbles.append(bubble)
            details.merge(cards) { first, _ in first }
        }
        let sources = response.sources ?? []
        return .init(
            id: groupID,
            bubbles: bubbles,
            highlights: details,
            confidence: response.confidence,
            links: (response.links ?? []).compactMap { PennyLink(rawValue: $0.rawValue) },
            sourceGroups: sourceGroups(sources, now: now),
            sourcesTitle: sourcesTitle(count: sources.count),
            disclaimer: response.disclaimer?.rawValue ?? disclaimer,
            modeLabel: modeLabel(response),
            isChecked: !isGeneral(response),
            suggestions: Array((response.suggestions ?? []).filter { !$0.isEmpty && $0.lowercased() != "yes" }.prefix(2)),
            isVerified: response.verified,
            isComplete: isComplete
        )
    }

    static func reaction(_ raw: String?) -> PennyReaction? {
        raw.flatMap(PennyReaction.init(rawValue:))
    }

    /// "2 messages · 17 Oct".
    static func threadSummary(_ thread: Components.Schemas.ChatThreadSummary) -> PennyViewState.ThreadSummary {
        let count = thread.messageCount == 1 ? "1 message" : "\(thread.messageCount) messages"
        var detail = count
        if let date = parseDate(thread.updatedAt) {
            let out = DateFormatter()
            out.locale = Locale(identifier: "en_GB")
            out.dateFormat = "d MMM"
            detail += " · " + out.string(from: date)
        }
        return .init(id: thread.id, title: thread.title, detail: detail)
    }

    /// "1 Reply", "3 Replies".
    static func repliesText(_ count: Int) -> String {
        count == 1 ? "1 Reply" : "\(count) Replies"
    }
}
