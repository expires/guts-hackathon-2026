import Foundation

/// "How Penny uses AI" (ADR 0043). Text from W5's `services/api/lifeline_explain/ai_disclosure.json`,
/// copied into the app as `Features/You/Resources/AIDisclosure.json`.
struct AIDisclosureViewState: Equatable, Sendable, Decodable {
    struct Section: Equatable, Sendable, Decodable, Identifiable {
        var heading: String
        var points: [String]
        var id: String { heading }
    }

    var title: String
    var sections: [Section]

    /// Shown when the bundled file is missing or unreadable.
    static let fallback = AIDisclosureViewState(
        title: "How \(Brand.productName) uses AI",
        sections: [
            .init(heading: "Where AI is used", points: ["An AI model rewords text on our server. The app never calls it."]),
            .init(heading: "What stays deterministic", points: ["Every number comes from your data, a public data source or the engine."]),
            .init(heading: "How output is checked", points: ["A number verifier checks every number in AI text against the engine's facts."]),
            .init(heading: "What happens when AI fails", points: ["The app shows the engine's template text. A number that fails the check is never shown."]),
        ]
    )

    static func load(bundle: Bundle = .main) -> AIDisclosureViewState {
        guard let url = bundle.url(forResource: "AIDisclosure", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let value = try? decode(data) else { return fallback }
        return value
    }

    static func decode(_ data: Data) throws -> AIDisclosureViewState {
        try JSONDecoder().decode(AIDisclosureViewState.self, from: data)
    }
}
