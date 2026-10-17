import Foundation

/// One open WebSocket to a Same Life room (`x-websocket` on `/v1/rooms/{code}`).
///
/// - The caller sends `join` first. To resume after a drop, open a new socket and send `join` with `player_id`.
/// - The socket never reconnects by itself.
/// - `messages` finishes when the socket closes or fails, or after `close()`.
/// - Messages that do not decode as `WsServerMessage` are skipped.
final class RoomSocket: Sendable {
    let messages: AsyncStream<WsServerMessage>
    private let sendHandler: @Sendable (WsClientMessage) async throws -> Void
    private let closeHandler: @Sendable () async -> Void

    init(
        messages: AsyncStream<WsServerMessage>,
        send: @escaping @Sendable (WsClientMessage) async throws -> Void,
        close: @escaping @Sendable () async -> Void
    ) {
        self.messages = messages
        self.sendHandler = send
        self.closeHandler = close
    }

    func send(_ message: WsClientMessage) async throws {
        try await sendHandler(message)
    }

    func close() async {
        await closeHandler()
    }

    /// `ws(s)://<host>/v1/rooms/<code>?token=<jwt>` from the REST base URL.
    static func url(baseURL: URL, code: String, token: String) -> URL? {
        guard var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else { return nil }
        components.scheme = components.scheme == "https" ? "wss" : "ws"
        let base = components.path.hasSuffix("/") ? String(components.path.dropLast()) : components.path
        components.path = base + "/v1/rooms/" + code
        components.queryItems = [URLQueryItem(name: "token", value: token)]
        return components.url
    }

    /// Live socket on `URLSessionWebSocketTask`.
    static func live(url: URL, session: URLSession = .shared) -> RoomSocket {
        let task = session.webSocketTask(with: url)
        let (stream, continuation) = AsyncStream.makeStream(of: WsServerMessage.self)
        let receiver = Task {
            let decoder = DiskCache.decoder  // accepts fractional-second dates
            while !Task.isCancelled {
                do {
                    let received = try await task.receive()
                    var data: Data?
                    switch received {
                    case let .string(text): data = Data(text.utf8)
                    case let .data(bytes): data = bytes
                    @unknown default: data = nil
                    }
                    if let data, let message = try? decoder.decode(WsServerMessage.self, from: data) {
                        continuation.yield(message)
                    }
                } catch {
                    break
                }
            }
            continuation.finish()
        }
        continuation.onTermination = { _ in
            receiver.cancel()
            task.cancel(with: .normalClosure, reason: nil)
        }
        task.resume()
        return RoomSocket(
            messages: stream,
            send: { message in
                let data = try JSONEncoder().encode(message)
                do {
                    try await task.send(.string(String(decoding: data, as: UTF8.self)))
                } catch {
                    throw APIError.network
                }
            },
            close: {
                task.cancel(with: .normalClosure, reason: nil)
                receiver.cancel()
                continuation.finish()
            }
        )
    }
}
