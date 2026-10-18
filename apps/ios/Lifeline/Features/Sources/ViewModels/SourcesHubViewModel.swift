import Foundation
import Observation

/// Loads the sources hub (`GET /v1/sources/hub`), cached first (ADR 0060): the saved copy shows at once,
/// the network copy replaces it quietly. Without a saved copy the screen shows a skeleton.
@MainActor
@Observable
final class SourcesHubViewModel {
    private let client: any LifelineClient
    private(set) var hub: SourcesHub?
    private var phase: LoadPhase = .loading(.standard)
    /// The card whose detail is open.
    var selectedID: String?
    /// The clock for "Updated 5 min ago". Tests pass a fixed date.
    private let now: @Sendable () -> Date

    @ObservationIgnored var onBack: @MainActor () -> Void = {}

    init(client: any LifelineClient, hub: SourcesHub? = nil, now: @escaping @Sendable () -> Date = { Date() }) {
        self.client = client
        self.now = now
        if let hub { show(hub) }
    }

    var state: SourcesHubViewState {
        guard let hub else { return SourcesHubViewState(phase: phase) }
        return SourcesHubMapping.state(hub, now: now())
    }

    /// The open detail, if the card still exists.
    var selectedCard: SourcesHubViewState.Card? {
        selectedID.flatMap { state.card(id: $0) }
    }

    var actions: SourcesHubActions {
        SourcesHubActions(
            onBack: { [weak self] in self?.onBack() },
            onRetry: { [weak self] in Task { await self?.load() } },
            onSelect: { [weak self] id in self?.selectedID = id }
        )
    }

    func show(_ hub: SourcesHub) {
        self.hub = hub
        phase = .ready
    }

    func load() async {
        if hub == nil { phase = .loading(.standard) }
        do {
            try await client.load(CachedOps.sourcesHub) { [weak self] value in self?.show(value) }
        } catch {
            if hub == nil { phase = .failed(.from(APIError.map(error))) }
        }
    }
}
