import Foundation
import Observation

/// What the backend sends back to the app after the Monzo sign-in:
/// `lifeline://connected?status=ok&provider=monzo&session=...` or `...?status=error&code=...`.
enum ConnectionReturn: Equatable, Sendable {
    case connected(provider: String, session: String?)
    case failed(code: String)

    /// Plain English text for a failed return. The backend sends a short code, never a message.
    static func message(for code: String) -> String {
        switch code {
        case "bad_state": "That sign-in link has expired. Start again."
        case "provider_auth", "auth": "Monzo did not accept the sign-in. Try again."
        case "rate_limited": "Monzo is busy. Try again in a minute."
        case "timeout", "unavailable", "bad_data": "Monzo is not answering right now. Try again soon."
        case "missing_code", "access_denied": "The Monzo sign-in was cancelled. Start again when you are ready."
        case "not_configured", "offline": "Monzo sign-in is not available on this server."
        default: "Could not connect Monzo. Try again."
        }
    }
}

/// Where a deep link wants to go.
enum DeepLink: Equatable, Sendable {
    case connection(ConnectionReturn)
    case join(code: String)

    /// Parses `lifeline://connected?...` and `lifeline://join/CODE`. Anything else is ignored.
    static func parse(_ url: URL) -> DeepLink? {
        guard url.scheme?.lowercased() == "lifeline", let host = url.host?.lowercased() else { return nil }
        switch host {
        case "connected":
            let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
            func value(_ name: String) -> String? { items.first(where: { $0.name == name })?.value }
            switch value("status") {
            case "ok":
                return .connection(.connected(provider: value("provider") ?? "monzo", session: value("session")))
            case "error":
                return .connection(.failed(code: value("code") ?? "unknown"))
            default:
                return nil
            }
        case "join":
            let code = url.pathComponents.dropFirst().first ?? ""
            return code.isEmpty ? nil : .join(code: code.uppercased())
        default:
            return nil
        }
    }
}

/// App tabs (ADR 0016). The game lives in Life.
enum AppTab: String, Hashable, CaseIterable {
    case money, life, you
}

/// Top-level navigation state and deep link handling. Glue only: Views never see it.
@MainActor
@Observable
final class AppCoordinator {
    var selectedTab: AppTab = .money
    /// Full-screen cover or sheet that any tab can request.
    var sheet: AppSheet?
    /// Increments for every connection return, so open screens can react with `.onChange`.
    private(set) var returnCount = 0
    /// Increments when a connection is added or removed, so the Money tab reloads.
    private(set) var connectionsVersion = 0
    private(set) var pendingReturn: ConnectionReturn?
    /// A Play yourself form is waiting for the Monzo sign-in. The return goes there instead of Accounts.
    var bankFlowAwaitingReturn = false
    private(set) var bankFlowReturn: ConnectionReturn?
    /// Room code from `lifeline://join/CODE`, for the Rooms screen to pick up.
    private(set) var pendingJoinCode: String?

    func handle(_ url: URL) {
        guard let link = DeepLink.parse(url) else { return }
        switch link {
        case let .connection(result):
            returnCount += 1
            if bankFlowAwaitingReturn {
                bankFlowReturn = result
                return
            }
            pendingReturn = result
            sheet = .accounts
        case let .join(code):
            pendingJoinCode = code
        }
    }

    /// Accounts calls this when it appears or sees a new return. Returns the return once.
    func takePendingReturn() -> ConnectionReturn? {
        defer { pendingReturn = nil }
        return pendingReturn
    }

    func takeBankFlowReturn() -> ConnectionReturn? {
        defer { bankFlowReturn = nil }
        return bankFlowReturn
    }

    func takeJoinCode() -> String? {
        defer { pendingJoinCode = nil }
        return pendingJoinCode
    }

    func connectionsChanged() { connectionsVersion += 1 }

    func openAccounts() { sheet = .accounts }
    func openInvestments() { sheet = .investments }
    func openHabits() { sheet = .habits }
}

enum AppSheet: String, Identifiable {
    case accounts, investments, habits, sources, store, debug
    var id: String { rawValue }
}
