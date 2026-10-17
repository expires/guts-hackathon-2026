import Foundation

/// Maps generated contract types to plain ViewState values. Used by all ViewModels.
enum StateMapping {
    static func status(_ raw: String) -> DataStatus {
        DataStatus(rawValue: raw) ?? .mock
    }

    static func sourceChip(_ ref: SourceRef) -> SourceChipState {
        SourceChipState(
            id: "\(ref.source).\(ref.seriesId)",
            name: sourceName(ref.source),
            status: status(ref.status.rawValue),
            note: ref.note
        )
    }

    /// Display names for source ids. Unknown ids are title-cased.
    static func sourceName(_ id: String) -> String {
        switch id {
        case "boe": "Bank of England"
        case "ons": "ONS"
        case "nomis": "Nomis"
        case "landregistry": "Land Registry"
        case "postcodes": "Postcodes.io"
        case "companies_house", "companieshouse": "Companies House"
        case "bank:fixtures", "fixtures", "bank": "Your bank"
        case "bank:sample", "sample": "Your statement"
        case "bank:statement", "statement": "Your statement"
        case "manual", "bank:manual": "Your numbers"
        case "govuk", "gov.uk", "gov_uk": "gov.uk"
        case "guardian": "The Guardian"
        default:
            // Never show an internal code such as "bank:xyz": the part before ":" names the kind of source.
            if id.hasPrefix("bank:") { "Your bank" } else { id.replacingOccurrences(of: "_", with: " ").capitalized }
        }
    }

    static func stats(_ stats: Components.Schemas.Stats) -> [StatState] {
        [
            StatState(kind: .happiness, value: stats.happiness),
            StatState(kind: .health, value: stats.health),
            StatState(kind: .smarts, value: stats.smarts),
            StatState(kind: .money, value: stats.money),
        ]
    }

    static func history(_ log: [YearLog]) -> [HistoryItemState] {
        log.enumerated().map { offset, entry in
            HistoryItemState(
                id: entry.decisionId ?? "h\(offset)",
                year: entry.year,
                age: entry.age,
                text: entry.text,
                netWorth: entry.netWorth,
                isDecision: entry.decisionId != nil
            )
        }
    }

    static func outcome(_ outcome: Outcome) -> OutcomeState {
        var changes: [String] = []
        let money = outcome.deltas.money ?? 0
        if money != 0 { changes.append(Money.signed(money)) }
        func add(_ title: String, _ value: Int?) {
            guard let value, value != 0 else { return }
            changes.append("\(title) \(value > 0 ? "+" : "")\(value)")
        }
        add("Happiness", outcome.deltas.happiness)
        add("Health", outcome.deltas.health)
        add("Smarts", outcome.deltas.smarts)
        return OutcomeState(text: outcome.text, isGood: outcome.good, moneyDelta: money, changes: changes)
    }

    static func chart(_ chart: Components.Schemas.Chart) -> ChartState {
        ChartState(
            kind: chart.kind == .bar ? .bar : .line,
            title: chart.title,
            xLabel: chart.xLabel,
            yLabel: chart.yLabel,
            points: chart.points.map { .init(x: $0.x, y: $0.y, label: $0.label) },
            source: chart.source.map(sourceChip)
        )
    }

    static func action(_ action: Components.Schemas.AvailableAction) -> ActionItemState {
        ActionItemState(
            id: action.id,
            emoji: action.emoji ?? "▶️",
            label: action.label,
            hint: action.hint,
            isEnabled: action.enabled ?? true,
            isPaid: action.paid ?? false
        )
    }

    static func actions(_ life: Life?, tab: Components.Schemas.AvailableAction.TabPayload) -> [ActionItemState] {
        (life?.availableActions ?? []).filter { $0.tab == tab }.map(action)
    }
}
