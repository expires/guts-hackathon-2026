import Foundation

/// Preview and test states for the sources hub (ADR 0073).
enum SourcesHubFixtures {
    /// A fixed clock, so previews and tests show the same relative times.
    static let now = Date(timeIntervalSince1970: 1_792_234_800)
    static var ready: SourcesHubViewState { SourcesHubMapping.state(SourcesHubMock.hub(now: now), now: now) }
    static var loading: SourcesHubViewState { SourcesHubViewState(phase: .loading(.standard)) }
    static var boe: SourcesHubViewState.Card { ready.card(id: "boe")! }
}
