import Foundation

/// Fixtures for "Test it" (W7). Kept in the feature folder so W6's `Fixtures.swift` needs no edit.
/// `result` is the contract example `TestMoveResult` (contracts/openapi.yaml), with the same values.
/// The other results are edited copies of it. Every state goes through `TestItViewModel.makeState`.
@MainActor
enum TestItFixtures {
    // MARK: Contract data

    static let result: Components.Schemas.TestMoveResult = ContractExamples.decode(json)

    /// Three options, sample sources, missed payments on the tracker. For layout and the "Sample data" badge.
    static var sampleThreeOptions: Components.Schemas.TestMoveResult {
        var value = result
        var tracker = value.outcomes[1]
        tracker.optionId = "tracker"
        tracker.label = "Tracker rate"
        tracker.lifeId = "lf_ttr001"
        tracker.netWorthPath = [
            .init(date: "2021-12-31", value: 66_000),
            .init(date: "2022-12-31", value: 67_400),
            .init(date: "2023-12-31", value: 69_100),
        ]
        tracker.endNetWorth = 69_100
        tracker.totalCost = 46_300
        tracker.missedPayments = 2
        tracker.worstYear = 2022
        tracker.worstYearChange = 1_400
        tracker.index = 96.1
        value.outcomes.append(tracker)
        value.sources = value.sources.map { source in
            var copy = source
            copy.status = .mock
            copy.note = "Sample numbers. Key not set on the server."
            return copy
        }
        return value
    }

    /// One option only (the API was asked for one option id).
    static var singleOption: Components.Schemas.TestMoveResult {
        var value = result
        value.outcomes = [value.outcomes[0]]
        return value
    }

    /// Mixed freshness: one live, one saved copy, one sample source.
    static var mixedSources: Components.Schemas.TestMoveResult {
        var value = result
        value.sources[1].status = .cached
        value.sources[2].status = .mock
        value.sources[2].note = "Sample numbers. Key not set on the server."
        return value
    }

    /// Real engine output for the demo persona: `Preview/Recorded/testNextMove.json`, as served by
    /// `MockClient(data: .recorded)` in the Mock build. Falls back to the contract example when the file is missing.
    static var recordedResult: Components.Schemas.TestMoveResult { MockData.recorded.testMoveResult }

    // MARK: View states

    /// What the Mock build shows: hero and summary from the recorded engine output.
    static var recorded: TestItViewState { TestItViewModel.makeState(result: recordedResult, phase: .ready) }

    static var ready: TestItViewState { TestItViewModel.makeState(result: result, phase: .ready) }
    static var sampleData: TestItViewState { TestItViewModel.makeState(result: sampleThreeOptions, phase: .ready) }
    static var mixed: TestItViewState { TestItViewModel.makeState(result: mixedSources, phase: .ready) }
    static var single: TestItViewState { TestItViewModel.makeState(result: singleOption, phase: .ready) }
    static var loading: TestItViewState {
        TestItViewModel.makeState(result: nil, phase: .loading(.init(message: TestItViewModel.loadingMessage)))
    }
    static var offline: TestItViewState {
        TestItViewModel.makeState(result: nil, phase: .failed(.from(.network)))
    }
    static var notFound: TestItViewState {
        TestItViewModel.makeState(
            result: nil,
            phase: .failed(.from(.server(status: 404, code: "not_found", message: "Move mv_x not found.", source: "api")))
        )
    }

    /// Every state with a Playground title. W6 lists these in the gallery.
    static var all: [(id: String, title: String, state: TestItViewState)] {
        [
            ("testit.recorded", "Mock build: recorded engine output", recorded),
            ("testit.ready", "Fix for 5 years against 2 years", ready),
            ("testit.sample", "Three options, sample data, missed payments", sampleData),
            ("testit.mixed", "Live, saved copy and sample sources", mixed),
            ("testit.single", "One option", single),
            ("testit.loading", "Loading", loading),
            ("testit.offline", "Offline error", offline),
            ("testit.notFound", "Move not found (404)", notFound),
        ]
    }

    // MARK: Loaders

    /// Returns the contract example at once. For the Playground until `MockClient.testNextMove` exists.
    static let mockLoader: TestItLoader = { _, optionIDs in
        let base = await result
        guard let optionIDs, !optionIDs.isEmpty else { return base }
        var filtered = base
        filtered.outcomes = base.outcomes.filter { optionIDs.contains($0.optionId) }
        return filtered
    }

    static let offlineLoader: TestItLoader = { _, _ in throw APIError.network }

    // MARK: JSON (contracts/openapi.yaml components.examples.TestMoveResult)

    static let json = #"""
    {
      "move_id": "mv_fix_mortgage",
      "period": {"start": 2021, "end": 2023, "label": "2021-2023 rate shock"},
      "character": {
        "name": "You", "emoji": "🙂", "sex": "female", "occupation": "analyst",
        "region": "yorkshire-and-the-humber", "town": "Leeds", "birth_year": 1992,
        "annual_income": 38000.0, "savings": 6200.0, "debt": 0.0, "housing": "mortgage",
        "property_value": 240000.0, "mortgage_balance": 180000.0
      },
      "outcomes": [
        {
          "option_id": "fix_5y", "label": "Fix for 5 years", "is_recommended": true, "life_id": "lf_t5y001",
          "net_worth_path": [
            {"date": "2021-12-31", "value": 66000.0},
            {"date": "2022-12-31", "value": 71200.0},
            {"date": "2023-12-31", "value": 77900.0}
          ],
          "end_net_worth": 77900.0, "total_cost": 37800.0, "missed_payments": 0,
          "worst_year": 2022, "worst_year_change": 5200.0, "index": 104.2
        },
        {
          "option_id": "fix_2y", "label": "Fix for 2 years", "is_recommended": false, "life_id": "lf_t2y001",
          "net_worth_path": [
            {"date": "2021-12-31", "value": 66000.0},
            {"date": "2022-12-31", "value": 70100.0},
            {"date": "2023-12-31", "value": 73720.0}
          ],
          "end_net_worth": 73720.0, "total_cost": 41980.0, "missed_payments": 0,
          "worst_year": 2023, "worst_year_change": 3620.0, "index": 100.0
        }
      ],
      "summary": "Fixing for 5 years left you £4,180 better off by 2023.",
      "evidence_sentence": "7 in 10 twins in similar past periods did better.",
      "sources": [
        {"source": "boe", "series_id": "IUMBV42", "status": "live"},
        {"source": "boe", "series_id": "IUMBV34", "status": "live"},
        {"source": "boe", "series_id": "IUMBEDR", "status": "live"}
      ]
    }
    """#
}
