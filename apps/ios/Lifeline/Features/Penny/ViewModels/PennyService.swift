import Foundation

/// Contract types for Ask Penny (ADR 0031). Only the Penny ViewModel, mapping and tests use them.
/// Views never see them (ADR 0011).
enum PennyAPI {
    typealias Request = Components.Schemas.ChatRequest
    typealias Context = Components.Schemas.ChatContext
    typealias Response = Components.Schemas.ChatResponse
    typealias Bubble = Components.Schemas.ChatBubble
    typealias Fact = Components.Schemas.ChatFact
    typealias Source = Components.Schemas.ChatSource
    typealias Highlight = Components.Schemas.Highlight
    typealias StreamEvent = Components.Schemas.ChatStreamEvent
    typealias Thread = Components.Schemas.ChatThread
    typealias Message = Components.Schemas.ChatMessage
    typealias ThreadsResponse = Components.Schemas.ChatThreadsResponse
}

/// The four chat operations as closures, so Penny builds and tests without a real client.
/// `PennyService.live(_:)` wraps `LifelineClient` once its chat methods land (BOSS helper, ADR 0037).
struct PennyService: Sendable {
    /// `POST /v1/chat` (non-streaming). The fallback when the stream fails.
    var ask: @Sendable (PennyAPI.Request) async throws -> PennyAPI.Response
    /// `POST /v1/chat/stream`: reaction, tool steps, verifying, bubbles, done.
    var stream: @Sendable (PennyAPI.Request) -> AsyncThrowingStream<PennyAPI.StreamEvent, Error>
    /// `GET /v1/chat/threads`, disk cache first (ADR 0060): `onUpdate` runs with the cached list at once,
    /// then again with the network list.
    var loadThreads: @Sendable (_ onUpdate: @escaping @MainActor @Sendable (PennyAPI.ThreadsResponse) -> Void) async throws -> Void
    /// `GET /v1/chat/threads/{id}`.
    var getThread: @Sendable (String) async throws -> PennyAPI.Thread

    /// Waits between bubbles (typing pause). Tests pass a recorder that returns at once.
    var sleep: @Sendable (Duration) async throws -> Void = { try await Task.sleep(for: $0) }
    /// "Updated X ago" is measured from this clock. Tests pin it.
    var now: @Sendable () -> Date = { Date() }
}

extension PennyService {
    /// Wraps the shared client (ADR 0011). `askPennyStream` yields one event per SSE `data:` line.
    static func live(_ client: any LifelineClient) -> PennyService {
        PennyService(
            ask: { try await client.askPenny($0) },
            stream: { client.askPennyStream($0) },
            loadThreads: { onUpdate in try await client.load(CachedOps.chatThreads, onUpdate: onUpdate) },
            getThread: { try await client.getChatThread(id: $0) }
        )
    }
}
