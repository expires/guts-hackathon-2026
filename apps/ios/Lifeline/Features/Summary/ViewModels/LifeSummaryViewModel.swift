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

    init(client: any LifelineClient, lifeID: String, emoji: String) {
        self.client = client
        self.lifeID = lifeID
        self.emoji = emoji
    }

    var state: LifeSummaryViewState {
        Self.makeState(summary: summary, emoji: emoji, phase: phase)
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

    static func makeState(summary: LifeSummary?, emoji: String, phase: LoadPhase) -> LifeSummaryViewState {
        guard let summary else {
            return LifeSummaryViewState(
                phase: phase, emoji: emoji, name: "", born: 0, died: nil, age: 0, causeOfDeath: nil,
                finalIndex: 100, netWorth: 0, autopilotNetWorth: 0, ribbons: [], keyMoments: [],
                conceptsUnlocked: 0, timeline: []
            )
        }
        return LifeSummaryViewState(
            phase: phase,
            emoji: emoji,
            name: summary.name,
            born: summary.born,
            died: summary.died,
            age: summary.age,
            causeOfDeath: summary.causeOfDeath,
            finalIndex: summary.finalIndex,
            netWorth: summary.netWorth,
            autopilotNetWorth: summary.autopilotNetWorth,
            ribbons: summary.ribbons.map { .init(id: $0.id, emoji: $0.emoji, title: $0.title, reason: $0.reason) },
            keyMoments: summary.keyMoments.enumerated().map { offset, moment in
                .init(id: "m\(offset)", year: moment.year, age: moment.age, emoji: moment.emoji, text: moment.text)
            },
            conceptsUnlocked: summary.conceptsUnlocked,
            timeline: summary.timeline.map { .init(year: $0.year, netWorth: $0.netWorth, autopilotNetWorth: $0.autopilotNetWorth) }
        )
    }
}
