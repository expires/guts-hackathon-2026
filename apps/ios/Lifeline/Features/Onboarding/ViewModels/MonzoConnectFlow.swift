import Foundation

/// The Monzo connect flow shared by onboarding and the connections screen: Monzo's sign-in opens in Safari,
/// the app waits for the backend to hold the sign-in, then retries the history import until the user approves
/// access in the Monzo app. The pop-up (`MonzoWaitSheetView`) shows `wait`. The caller decides what happens
/// after the approval (`onApproved`): onboarding builds the profile, the connections screen refreshes.
@MainActor
final class MonzoConnectFlow {
    /// The backend calls the flow needs.
    struct API: Sendable {
        var bankAuthLink: @Sendable (_ provider: String) async throws -> BankAuthLink
        var monzoConnected: @Sendable () async throws -> Bool
        var syncMonzo: @Sendable () async throws -> MonzoHistory
    }

    private let api: API

    /// The pop-up state. Nil: no pop-up.
    private(set) var wait: MonzoWait? {
        didSet { if wait != oldValue { onWaitChange(wait) } }
    }

    // Platform hook, set by the glue.
    var openInSafari: (@MainActor (URL) -> Void)?

    // Caller hooks.
    var onWaitChange: @MainActor (MonzoWait?) -> Void = { _ in }
    /// False when the caller's screen has moved on: the approval wait stops.
    var shouldContinue: @MainActor () -> Bool = { true }
    /// The server is not set up for Monzo (or Safari is missing).
    var onUnavailable: @MainActor () -> Void = {}
    /// A plain-English error for the caller's screen.
    var onError: @MainActor (String) -> Void = { _ in }
    /// Approved and ready to import. The flow shows "Importing" meanwhile and clears the pop-up afterwards.
    var onApproved: @MainActor (_ session: String) async -> Void = { _ in }

    /// While Monzo sign-in is open in Safari, ask the backend every `connectInterval` whether Monzo is connected.
    var connectInterval: Duration = .seconds(3)
    var connectLimit = 200
    /// Monzo only shares data after the user approves access in the Monzo app (it answers 403 until then).
    /// Retry the import every `pollInterval` for up to five minutes.
    var pollInterval: Duration = .seconds(5)
    var pollLimit = 60
    private(set) var task: Task<Void, Never>?
    private var url: URL?
    private var session = ""
    /// True when the pop-up failed at the approval wait, so Try again repeats only that wait.
    private var approvalFailed = false

    init(api: API) {
        self.api = api
    }

    /// "Connect Monzo": gets the sign-in link, opens Safari, starts waiting.
    func start() async {
        do {
            let link = try await api.bankAuthLink("monzo")
            guard link.status != .unavailable, let url = URL(string: link.url) else { return onUnavailable() }
            guard let openInSafari else { return onUnavailable() }
            self.url = url
            session = link.state
            approvalFailed = false
            wait = .signingIn
            openInSafari(url)
            startPolling()
        } catch let error as APIError {
            if case let .server(status, _, _, _) = error, status == 409 || status == 501 || status == 503 {
                onUnavailable()
            } else {
                onError(error.userMessage)
            }
        } catch {
            onError(L10n.tr("Monzo was not connected. Try again, or use another way."))
        }
    }

    private func startPolling() {
        task?.cancel()
        task = Task { [weak self] in await self?.waitForConnection() }
    }

    private func waitForConnection() async {
        for attempt in 0..<connectLimit {
            guard !Task.isCancelled, wait == .signingIn else { return }
            if (try? await api.monzoConnected()) == true {
                guard !Task.isCancelled, wait == .signingIn else { return }
                wait = .approving
                await approveAndImport()
                return
            }
            guard attempt + 1 < connectLimit else { break }
            try? await Task.sleep(for: connectInterval)
        }
        guard !Task.isCancelled, wait == .signingIn else { return }
        fail(L10n.tr("Monzo sign-in took too long. Try again."), atApproval: false)
    }

    private func approveAndImport() async {
        let approved = await waitForApproval()
        guard wait == .approving, !Task.isCancelled else { return }
        guard approved else {
            return fail(
                L10n.tr("Monzo has not shared your history yet. Approve the request in your Monzo app, then try again."),
                atApproval: true
            )
        }
        wait = .importing
        await onApproved(session)
        if wait == .importing { wait = nil }
    }

    private func waitForApproval() async -> Bool {
        for attempt in 0..<pollLimit {
            do {
                if try await api.syncMonzo().synced { return true }
            } catch {
                // A server without connections (501) has nothing to wait for. Other errors: keep trying.
                if case let .server(status, _, _, _) = APIError.map(error), status == 501 { return true }
            }
            guard attempt + 1 < pollLimit else { break }
            try? await Task.sleep(for: pollInterval)
            if Task.isCancelled || wait != .approving || !shouldContinue() { return false }
        }
        return false
    }

    private func fail(_ message: String, atApproval: Bool) {
        task?.cancel()
        approvalFailed = atApproval
        wait = .failed(message)
    }

    /// Cancel or Close on the pop-up: stops every wait.
    func cancel() {
        task?.cancel()
        task = nil
        wait = nil
    }

    /// "Open Safari again" while signing in.
    func reopenSafari() {
        guard wait == .signingIn, let url else { return }
        openInSafari?(url)
    }

    /// "Try again" after a failure: repeats only the approval wait, or starts the sign-in again.
    func retry() {
        guard case .failed = wait else { return }
        task?.cancel()
        if approvalFailed {
            wait = .approving
            task = Task { [weak self] in await self?.approveAndImport() }
        } else if let url {
            wait = .signingIn
            openInSafari?(url)
            startPolling()
        } else {
            wait = nil
        }
    }

    /// The app came back to the front, or `lifeline://connected` arrived: check for a connection at once.
    func recheck() {
        guard wait == .signingIn else { return }
        startPolling()
    }

    /// `lifeline://connected?status=ok|error&code=...` (Monzo's redirect, after the backend stored the sign-in).
    func handleConnectedURL(_ url: URL) {
        guard url.scheme == "lifeline", url.host() == "connected", wait != nil else { return }
        let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        func value(_ name: String) -> String? { items.first { $0.name == name }?.value }
        if value("status") == "error" {
            guard wait == .signingIn else { return }
            fail(Self.errorMessage(code: value("code")), atApproval: false)
        } else {
            recheck()
        }
    }

    static func errorMessage(code: String?) -> String {
        switch code {
        case "access_denied": L10n.tr("You cancelled the Monzo sign-in.")
        case "bad_state": L10n.tr("That sign-in link expired. Try again.")
        case "provider_auth": L10n.tr("Monzo did not accept the sign-in. Try again.")
        default: L10n.tr("Monzo was not connected. Try again, or use another way.")
        }
    }
}
