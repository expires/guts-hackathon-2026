import Foundation
import HTTPTypes
import OpenAPIRuntime

extension APIError {
    /// Code for a request that stayed rate limited (429) after the quiet retries.
    static let rateLimitedQuietCode = "rate_limited_quiet"

    /// The calm error after the quiet retries. The UI shows its message as is.
    /// Computed, so the message follows the current app language (ADR 0063).
    static var rateLimitedQuiet: APIError { .server(
        status: 429,
        code: rateLimitedQuietCode,
        message: L10n.tr("Couldn't load. Pull to refresh."),
        source: "client"
    ) }
}

/// Retries a 429 response quietly, with exponential backoff that honours `Retry-After`.
/// At most `maxAttempts` tries and `maxTotalWait` seconds of waiting. After that it throws `APIError.rateLimitedQuiet`.
/// Requests with a body that cannot be sent again (a one-shot stream) are not retried.
struct RateLimitRetryMiddleware: ClientMiddleware {
    var maxAttempts = 3
    var baseDelay: Double = 0.5
    var maxTotalWait: Double = 10

    func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        let replayable = body == nil || body?.iterationBehavior == .multiple
        var waited: Double = 0
        var attempt = 1
        while true {
            let (response, responseBody) = try await next(request, body, baseURL)
            guard response.status.code == 429 else { return (response, responseBody) }
            guard replayable, attempt < maxAttempts else { throw APIError.rateLimitedQuiet }
            let backoff = baseDelay * pow(2, Double(attempt - 1))
            let delay = min(max(Self.retryAfter(response) ?? backoff, backoff), maxTotalWait - waited)
            guard delay > 0 else { throw APIError.rateLimitedQuiet }
            try await Task.sleep(for: .seconds(delay))
            waited += delay
            attempt += 1
        }
    }

    /// `Retry-After` in seconds (the delay-seconds form only).
    static func retryAfter(_ response: HTTPResponse) -> Double? {
        guard let name = HTTPField.Name("Retry-After"),
              let raw = response.headerFields[name] else { return nil }
        return Double(raw.trimmingCharacters(in: .whitespaces))
    }
}

/// Short-lived GET cache with in-flight de-duplication.
///
/// - Identical GETs (same path and query) that run at the same time share one network call.
/// - A 2xx GET response is reused for `ttl` seconds, so a tab that appears again does not refetch.
/// - Any non-GET request clears the cache, because it can change what a GET returns.
/// - `clear()` drops everything (pull to refresh).
actor ResponseCache {
    typealias Value = (response: HTTPResponse, data: Data)

    enum Lookup: Sendable {
        /// Use this value.
        case hit(HTTPResponse, Data)
        /// No fresh value and no call in flight: the caller loads, then calls `finish`.
        case load(generation: Int)
    }

    struct Entry: Sendable {
        let response: HTTPResponse
        let data: Data
        let stored: ContinuousClock.Instant
    }

    let ttl: Duration
    private var entries: [String: Entry] = [:]
    private var waiters: [String: [CheckedContinuation<Value, any Error>]] = [:]
    private var generation = 0

    init(ttl: Duration = .seconds(20)) {
        self.ttl = ttl
    }

    func clear() {
        entries = [:]
        generation += 1
    }

    func begin(_ key: String) async throws -> Lookup {
        if let entry = entries[key], ContinuousClock.now - entry.stored < ttl {
            return .hit(entry.response, entry.data)
        }
        if waiters[key] != nil {
            let value = try await withCheckedThrowingContinuation { continuation in
                waiters[key, default: []].append(continuation)
            }
            return .hit(value.response, value.data)
        }
        waiters[key] = []
        return .load(generation: generation)
    }

    func finish(_ key: String, generation started: Int, result: Result<Value, any Error>) {
        if case let .success(value) = result, started == generation, (200..<300).contains(value.response.status.code) {
            entries[key] = Entry(response: value.response, data: value.data, stored: .now)
        }
        for waiter in waiters[key] ?? [] { waiter.resume(with: result) }
        waiters[key] = nil
    }
}

struct ResponseCacheMiddleware: ClientMiddleware {
    /// Operations that must always be fresh.
    static let uncached: Set<String> = ["getHealth", "getRoom", "getBankSummary", "bankCallback"]
    /// Largest body that the cache keeps. Larger bodies pass through.
    static let maxBodyBytes = 8 * 1024 * 1024

    let cache: ResponseCache

    func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        guard request.method == .get else {
            await cache.clear()
            return try await next(request, body, baseURL)
        }
        guard !Self.uncached.contains(operationID) else {
            return try await next(request, body, baseURL)
        }
        let key = operationID + " " + (request.path ?? "")
        switch try await cache.begin(key) {
        case let .hit(response, data):
            return (response, HTTPBody(data))
        case let .load(generation):
            do {
                let (response, responseBody) = try await next(request, body, baseURL)
                var data = Data()
                if let responseBody {
                    data = try await Data(collecting: responseBody, upTo: Self.maxBodyBytes)
                }
                await cache.finish(key, generation: generation, result: .success((response, data)))
                return (response, HTTPBody(data))
            } catch {
                await cache.finish(key, generation: generation, result: .failure(error))
                throw error
            }
        }
    }
}
