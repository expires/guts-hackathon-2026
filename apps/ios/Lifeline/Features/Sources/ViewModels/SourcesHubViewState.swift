import Foundation

/// "Where Penny's data comes from" (ADR 0073): the summary, one card per student-facing source and, on tap,
/// the source's latest values with a link to the official page.
struct SourcesHubViewState: Equatable, Sendable {
    struct Value: Equatable, Sendable, Identifiable {
        var id: Int
        /// "Easy-access savings rate".
        var label: String
        /// "2.06%".
        var value: String
        /// "As of Sep 2026". Nil when the server sends no date.
        var asOfText: String?
    }

    struct Card: Equatable, Sendable, Identifiable {
        var id: String
        /// "Bank of England".
        var name: String
        var status: DataStatus
        /// "Live", "Saved copy", "Not live now", "Unavailable", or "Checked figures" for official facts.
        var statusText: String
        /// "Updated 5 min ago". Nil without a time.
        var updatedText: String?
        /// One line from the server: what the source gives Penny.
        var gives: String
        /// "Used in: One thing that helps, The maths". Nil when the list is empty.
        var usedInText: String?
        var latest: [Value]
        /// The official page. Nil hides "Open the official page".
        var url: URL?

        /// One sentence for VoiceOver.
        var accessibilitySummary: String {
            [name, statusText, updatedText, gives, usedInText].compactMap { $0 }.joined(separator: ". ")
        }
    }

    var phase: LoadPhase
    /// "Penny uses your statement plus 7 live UK sources. Here is what each one does."
    var summary: String = ""
    var liveCount: Int = 0
    var cards: [Card] = []

    func card(id: String) -> Card? { cards.first { $0.id == id } }
}

struct SourcesHubActions {
    var onBack: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}
    /// A card tap: shows that source's latest values.
    var onSelect: @MainActor (String) -> Void = { _ in }

    static var noop: Self { .init() }
}

/// Response to state. Pure, so tests check it without a client.
enum SourcesHubMapping {
    /// Live feeds a student sees (ADR 0073, PENNY_V3_BUILD B4). A live source with any other id
    /// (Land Registry, EPC, cut banks) is hidden, even if the server sends it.
    static let studentLiveIDs: Set<String> = ["boe", "ons", "nomis", "octopus", "frankfurter", "boe-mpc"]
    /// Homeowner and cut sources: never shown, whatever their kind.
    static let blockedTokens = ["landregistry", "land registry", "epc", "mortgage", "companieshouse", "truelayer", "monzo", "trading212", "adzuna", "dvla", "dvsa"]

    /// True for your statement, official facts and the student-facing live feeds.
    static func isStudentFacing(_ source: HubSource) -> Bool {
        let text = (source.id + " " + source.name).lowercased()
        if blockedTokens.contains(where: { text.contains($0) }) { return false }
        switch source.kind {
        case .statement, .officialFacts: return true
        case .live: return studentLiveIDs.contains(source.id)
        }
    }

    static func state(_ hub: SourcesHub, now: Date = Date()) -> SourcesHubViewState {
        SourcesHubViewState(
            phase: .ready,
            summary: hub.summary,
            liveCount: hub.liveCount,
            cards: hub.sources.filter(isStudentFacing).map { card($0, now: now) }
        )
    }

    static func card(_ source: HubSource, now: Date) -> SourcesHubViewState.Card {
        let status = StateMapping.status(source.status.rawValue)
        let statusText: String = switch (source.kind, status) {
        case (.officialFacts, .live), (.officialFacts, .cached): L10n.tr("Checked figures")
        case (_, .live): L10n.tr("Live")
        case (_, .cached): L10n.tr("Saved copy")
        case (_, .mock): L10n.tr("Not live now")
        case (_, .unavailable): L10n.tr("Unavailable")
        }
        let usedIn = source.usedIn.filter { !$0.isEmpty }
        return SourcesHubViewState.Card(
            id: source.id,
            name: source.name,
            status: status,
            statusText: statusText,
            updatedText: source.updatedAt.map { updatedText($0, now: now) },
            gives: source.gives,
            usedInText: usedIn.isEmpty ? nil : L10n.tr("Used in: \(usedIn.joined(separator: ", "))"),
            latest: (source.latest ?? []).enumerated().map { index, value in
                .init(
                    id: index, label: value.label, value: value.value,
                    asOfText: value.asOf.flatMap { $0.isEmpty ? nil : L10n.tr("As of \(asOfText($0))") }
                )
            },
            url: source.url.flatMap { URL(string: $0) }.flatMap { $0.scheme == "https" || $0.scheme == "http" ? $0 : nil }
        )
    }

    /// "Updated just now", "Updated 5 min ago", "Updated 3 h ago", "Updated 2 days ago".
    static func updatedText(_ date: Date, now: Date) -> String {
        let seconds = max(0, now.timeIntervalSince(date))
        switch seconds {
        case ..<60: return L10n.tr("Updated just now")
        case ..<3_600: return L10n.tr("Updated \(Int(seconds / 60)) min ago")
        case ..<86_400: return L10n.tr("Updated \(Int(seconds / 3_600)) h ago")
        default:
            let days = Int(seconds / 86_400)
            return days == 1 ? L10n.tr("Updated 1 day ago") : L10n.tr("Updated \(days) days ago")
        }
    }

    /// An ISO date ("2026-10-17") becomes "17 Oct 2026"; any other text ("Sep 2026") stays.
    static func asOfText(_ raw: String) -> String {
        guard raw.count == 10, let date = FinanceMapping.date(raw) else { return raw }
        return FinanceMapping.format(date, template: "dMMMyyyy")
    }

    /// "Based on 7 sources" for the forecast card: the forecast's own student-facing sources.
    static func basedOnText(count: Int) -> String? {
        guard count > 0 else { return nil }
        return count == 1 ? L10n.tr("Based on 1 source") : L10n.tr("Based on \(count) sources")
    }
}
