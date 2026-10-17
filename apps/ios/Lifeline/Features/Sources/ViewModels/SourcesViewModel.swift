import Foundation
import Observation

/// Data sources and attributions (`GET /v1/sources`).
@MainActor
@Observable
final class SourcesViewModel {
    private let client: any LifelineClient
    private(set) var sources: [SourceStatus] = []
    private(set) var phase: LoadPhase = .loading(.init(message: "Checking data sources"))
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: SourcesViewState {
        Self.makeState(sources: sources, phase: phase, usesSampleData: client.kind == .mock)
    }

    var actions: SourcesActions {
        SourcesActions(
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    func load() async {
        phase = .loading(.init(message: "Checking data sources"))
        do {
            sources = try await client.listSources()
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    static func makeState(sources: [SourceStatus], phase: LoadPhase, usesSampleData: Bool) -> SourcesViewState {
        SourcesViewState(
            phase: phase,
            rows: sources.map {
                .init(
                    id: $0.id,
                    name: $0.name,
                    status: StateMapping.status($0.status.rawValue),
                    updatedText: $0.fetchedAt.map { "Updated " + $0.formatted(.dateTime.day().month().year().hour().minute().locale(Money.locale)) },
                    coverage: $0.coverage,
                    attribution: $0.attribution,
                    licence: $0.licence,
                    needsKey: $0.needsKey ?? false,
                    lastError: $0.lastError
                )
            },
            usesSampleData: usesSampleData
        )
    }
}
