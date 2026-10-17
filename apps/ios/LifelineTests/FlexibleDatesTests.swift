import Foundation
import Testing
@testable import Lifeline

/// The API sends times with and without fractional seconds; both must decode (sources screen bug).
struct FlexibleDatesTests {
    @Test func decodesFractionalSeconds() throws {
        let date = try FlexibleISO8601Transcoder().decode("2026-10-17T21:10:10.491792Z")
        #expect(abs(date.timeIntervalSince1970 - 1_792_271_410.491) < 0.01)
    }

    @Test func decodesWholeSeconds() throws {
        let date = try FlexibleISO8601Transcoder().decode("2026-10-17T21:10:10Z")
        #expect(date.timeIntervalSince1970 == 1_792_271_410)
    }

    @Test func rejectsGarbage() {
        #expect(throws: (any Error).self) { try FlexibleISO8601Transcoder().decode("yesterday") }
    }
}
