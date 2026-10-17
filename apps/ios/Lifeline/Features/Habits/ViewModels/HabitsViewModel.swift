import Foundation
import Observation

/// Loads `GET /v1/finance/habits`. Labels and explainers come from the backend.
@MainActor
@Observable
final class HabitsViewModel {
    static let loadingMessage = "Looking at your habits"

    private let client: any LifelineClient
    private(set) var habits: HabitFactors?
    private(set) var connections: ConnectionsResponse?
    private(set) var phase: LoadPhase = .loading(.init(message: HabitsViewModel.loadingMessage))
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: HabitsViewState {
        Self.makeState(habits: habits, phase: phase, isSample: Self.isSample(connections: connections, clientKind: client.kind))
    }

    var actions: HabitsActions {
        HabitsActions(
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    func load() async {
        phase = .loading(.init(message: Self.loadingMessage))
        let client = self.client
        connections = try? await client.listConnections()
        do {
            habits = try await client.habits()
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    // MARK: Pure mapping (used by fixtures and tests)

    /// Habits come from your Monzo history. Without live Monzo data they come from sample data.
    static func isSample(connections: ConnectionsResponse?, clientKind: ClientKind) -> Bool {
        if clientKind == .mock { return true }
        guard let monzo = connections?.providers.first(where: { $0.provider == .monzo }) else { return true }
        return !(monzo.connected && monzo.dataStatus == .live)
    }

    static func band(_ score: Int) -> String {
        switch score {
        case 70...: "Going well"
        case 40..<70: "Fine for now"
        default: "Worth a look"
        }
    }

    static func makeState(habits: HabitFactors?, phase: LoadPhase, isSample: Bool) -> HabitsViewState {
        let factors = (habits?.factors ?? []).map { factor -> HabitsViewState.Factor in
            .init(
                id: factor.id.rawValue,
                label: factor.label,
                explainer: factor.explainer,
                score: factor.score,
                scoreText: factor.score.map { "\($0) out of 100" } ?? "Not enough data",
                bandText: factor.score.map(band),
                reason: factor.score == nil ? (factor.reason ?? "We need more history to work this out.") : nil
            )
        }
        let windowText = habits.map { habits -> String in
            let months = habits.window.months
            return "Last \(months == 1 ? "month" : "\(months) months"), up to \(FinanceMapping.dayText(habits.window.end))"
        } ?? ""
        return HabitsViewState(
            phase: phase,
            overall: habits?.overall,
            windowText: windowText,
            overallBandText: habits?.overall.map(band),
            factors: factors,
            isSampleData: isSample
        )
    }
}
