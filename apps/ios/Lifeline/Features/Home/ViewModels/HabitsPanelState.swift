import Foundation

/// The "Your habits" panel on Money home: the overall score, a few labelled bars and where the numbers came
/// from. Ratios only, never pounds.
struct HabitsPanelState: Equatable, Sendable {
    struct Row: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var value: Int
    }

    enum Phase: Equatable, Sendable {
        case loading
        case score
        /// No transactions yet, or the habits could not be worked out.
        case empty
    }

    var phase: Phase = .loading
    var overall: Int?
    var rows: [Row] = []
    /// "From Monzo", "From your statement" or "Sample data". Nil when the source is unknown.
    var sourceText: String?

    static var title: String { L10n.tr("Your habits") }
    static var caption: String {
        L10n.tr("Scores run from 0 to 100 and come from how you use your money, not how much you have.")
    }
    static var emptyText: String { L10n.tr("Connect Monzo or upload a statement to see your habits") }

    static let loading = HabitsPanelState()
    static let empty = HabitsPanelState(phase: .empty)

    /// Up to four of the most telling factors: the two lowest and the two highest, in the usual order.
    @MainActor static func make(_ score: HabitScore, meta: FinanceMeta?) -> HabitsPanelState {
        let all = ProfileStatsViewModel.habitRows(score).map { Row(id: $0.id, label: $0.label, value: min(100, max(0, $0.value))) }
        guard score.overall != nil || !all.isEmpty else { return .empty }
        let ranked = all.enumerated().sorted { ($0.element.value, $0.offset) < ($1.element.value, $1.offset) }
        var picked = Set(ranked.prefix(2).map(\.offset))
        picked.formUnion(ranked.suffix(2).map(\.offset))
        let rows = all.enumerated().filter { picked.contains($0.offset) }.map(\.element)
        return HabitsPanelState(phase: .score, overall: score.overall.map { Int($0) }, rows: rows, sourceText: sourceText(meta))
    }

    static func sourceText(_ meta: FinanceMeta?) -> String? {
        guard let meta else { return nil }
        if FinanceMapping.isSample(meta) { return L10n.tr("Sample data") }
        let source = meta.source.lowercased()
        if source.contains("monzo") { return L10n.tr("From Monzo") }
        if source.contains("statement") { return L10n.tr("From your statement") }
        return nil
    }

    var accessibilitySummary: String {
        switch phase {
        case .loading: L10n.tr("Loading")
        case .empty: Self.emptyText
        case .score:
            ([overall.map { L10n.tr("Habit score \($0) out of 100") }] + rows.map { "\($0.label), \($0.value)" } + [sourceText])
                .compactMap { $0 }.joined(separator: ". ")
        }
    }
}
