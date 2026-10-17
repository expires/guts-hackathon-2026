import Foundation
import OpenAPIRuntime

/// The API sends RFC 3339 times with or without fractional seconds (e.g. "2026-10-17T21:10:10.491792Z").
/// The generator's default transcoder rejects fractional seconds, so every client uses this one.
struct FlexibleISO8601Transcoder: DateTranscoder {
    func encode(_ date: Date) throws -> String {
        date.ISO8601Format(.iso8601.time(includingFractionalSeconds: true))
    }

    func decode(_ string: String) throws -> Date {
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = fractional.date(from: string) { return date }
        if let date = ISO8601DateFormatter().date(from: string) { return date }
        throw DecodingError.dataCorrupted(.init(codingPath: [], debugDescription: "Bad date: \(string)"))
    }
}
