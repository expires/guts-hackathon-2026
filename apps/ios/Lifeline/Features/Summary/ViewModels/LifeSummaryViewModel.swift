import Foundation
import Observation

/// Life Summary: ribbons, final Index, net worth, key moments.
@MainActor
@Observable
final class LifeSummaryViewModel {
    private let client: any LifelineClient
    private let lifeID: String
    private let emoji: String
    private(set) var summary: LifeSummary?
    private(set) var phase: LoadPhase = .loading(.init(message: "Adding up your life"))
    @ObservationIgnored var onNewLife: @MainActor () -> Void = {}
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    private let usesSampleData: Bool

    init(client: any LifelineClient, lifeID: String, emoji: String) {
        self.usesSampleData = client.kind == .mock
        self.client = client
        self.lifeID = lifeID
        self.emoji = emoji
    }

    var state: LifeSummaryViewState {
        Self.makeState(summary: summary, emoji: emoji, phase: phase, usesSampleData: usesSampleData)
    }

    var actions: LifeSummaryActions {
        LifeSummaryActions(
            onNewLife: { [weak self] in self?.onNewLife() },
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    func load() async {
        phase = .loading(.init(message: "Adding up your life"))
        do {
            summary = try await client.summary(lifeID: lifeID)
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    static func makeState(
        summary: LifeSummary?,
        emoji: String,
        phase: LoadPhase,
        usesSampleData: Bool = false
    ) -> LifeSummaryViewState {
        guard let summary else {
            return LifeSummaryViewState(
                phase: phase, emoji: emoji, name: "", born: 0, died: nil, age: 0, causeOfDeath: nil,
                finalIndex: 100, netWorth: 0, autopilotNetWorth: 0, ribbons: [], keyMoments: [],
                conceptsUnlocked: 0, timeline: []
            )
        }
        let timeline = summary.timeline
        let finalIndex = summary.finalIndex
        let gap = (finalIndex - RewindViewModel.autopilotIndex).rounded()
        let indexSentence = gap == 0
            ? "Level with your autopilot twin."
            : "\(Int(abs(gap))) points \(gap > 0 ? "ahead of" : "behind") your autopilot twin."
        let lifespan = summary.died.map { "\(String(summary.born)) to \(String($0)) · lived to \(summary.age)" }
            ?? "Born \(String(summary.born)) · age \(summary.age)"
        let ribbons = summary.ribbons.map { LifeSummaryViewState.Ribbon(id: $0.id, emoji: $0.emoji, title: $0.title, reason: $0.reason) }
        let share = [
            "\(summary.name)'s life in \(Brand.productName): \(lifespan).",
            "INDEX \(Int(finalIndex.rounded())). \(indexSentence)",
            "Net worth \(Money.format(summary.netWorth)) against \(Money.format(summary.autopilotNetWorth)) on autopilot.",
            ribbons.isEmpty ? nil : "Ribbons: " + ribbons.map(\.title).joined(separator: ", ") + ".",
        ].compactMap { $0 }.joined(separator: " ")
        return LifeSummaryViewState(
            phase: phase,
            emoji: emoji,
            name: summary.name,
            born: summary.born,
            died: summary.died,
            age: summary.age,
            causeOfDeath: summary.causeOfDeath,
            finalIndex: finalIndex,
            netWorth: summary.netWorth,
            autopilotNetWorth: summary.autopilotNetWorth,
            ribbons: ribbons,
            keyMoments: summary.keyMoments.enumerated().map { offset, moment in
                let delta = indexDelta(year: moment.year, timeline: timeline)
                return .init(
                    id: "m\(offset)", year: moment.year, age: moment.age, emoji: moment.emoji, text: moment.text,
                    indexDelta: delta.map(signedText), isDown: (delta ?? 0) < 0
                )
            },
            conceptsUnlocked: summary.conceptsUnlocked,
            timeline: timeline.map {
                .init(year: $0.year, netWorth: $0.netWorth, autopilotNetWorth: $0.autopilotNetWorth, age: $0.age)
            },
            title: "\(summary.name)'s life",
            lifespanText: lifespan,
            indexText: "\(Int(finalIndex.rounded()))",
            indexSentence: indexSentence,
            shareText: share,
            isSampleData: usesSampleData
        )
    }

    /// Index change from the timeline entry before the moment's year to the entry at (or after) it.
    static func indexDelta(year: Int, timeline: [Components.Schemas.YearLog]) -> Double? {
        let sorted = timeline.sorted { $0.year < $1.year }
        guard let at = sorted.firstIndex(where: { $0.year >= year }), at > 0 else { return nil }
        return sorted[at].index - sorted[at - 1].index
    }

    /// "+3", "-4", "0".
    static func signedText(_ value: Double) -> String {
        let rounded = Int(value.rounded())
        return rounded > 0 ? "+\(rounded)" : "\(rounded)"
    }
}
