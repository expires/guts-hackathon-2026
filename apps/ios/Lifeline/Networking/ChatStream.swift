import Foundation
import OpenAPIRuntime

/// Decodes the `POST /v1/chat/stream` body (Server-Sent Events, ADR 0031 amendment).
/// Each `data:` line holds one `ChatStreamEvent` as JSON. The stream ends after the `done` event.
enum ChatStream {
    /// Turns an SSE body into events. Lines that are not valid events are skipped.
    static func events(from body: HTTPBody) -> AsyncThrowingStream<ChatStreamEvent, any Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    let decoder = DiskCache.decoder  // accepts fractional-second dates
                    for try await event in body.asDecodedServerSentEvents() {
                        guard let payload = event.data, !payload.isEmpty,
                              let decoded = try? decoder.decode(ChatStreamEvent.self, from: Data(payload.utf8)) else {
                            continue
                        }
                        continuation.yield(decoded)
                        if decoded._type == .done { break }
                    }
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: APIError.map(error))
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }
}
