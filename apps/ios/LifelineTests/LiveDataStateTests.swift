import Testing
@testable import Lifeline

/// Live data mode (Demo build): 409 `no_finance_data` and the `unavailable` source status.
@MainActor
struct LiveDataStateTests {
    @Test func noFinanceDataPointsToOnboarding() {
        let error = APIError.server(status: 409, code: "no_finance_data", message: "Connect your money first.", source: "api")
        let state = ErrorViewState.from(error)
        #expect(error.isNoFinanceData)
        #expect(state.isUnavailable)
        #expect(state.title == "Connect your money first")
        #expect(state.message.contains("Play yourself"))
    }

    @Test func otherErrorsKeepTheCrashState() {
        #expect(!ErrorViewState.from(.network).isUnavailable)
    }

    @Test func unavailableStatusMapsAndRanksWorst() {
        #expect(StateMapping.status("unavailable") == .unavailable)
        #expect(DataStatus.unavailable.label == "unavailable")
    }
}
