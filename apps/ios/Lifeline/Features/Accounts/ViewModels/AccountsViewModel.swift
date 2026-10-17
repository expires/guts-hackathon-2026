import Foundation
import Observation

/// Loads `GET /v1/connections`, connects and disconnects providers, and keeps retrying the Monzo history
/// import while the screen is visible and Monzo is waiting for approval.
@MainActor
@Observable
final class AccountsViewModel {
    static let loadingMessage = "Loading your accounts"
    static let approvalMessage = "Approve the request in your Monzo app. Your history imports automatically once you do."
    static let monzoGuidance = "Open the email from Monzo on this iPhone, then approve in the Monzo app."
    static let trading212Guidance = "Create an API key in the Trading212 app. It comes as a key and a secret. Works for Invest and Stocks ISA accounts."

    /// How long to wait between history imports, and how long to keep trying.
    static let syncInterval: Duration = .seconds(5)
    static let syncLimit: Duration = .seconds(300)

    typealias Sleeper = @Sendable (Duration) async throws -> Void

    private let client: any LifelineClient
    private let sleep: Sleeper

    private(set) var connections: ConnectionsResponse?
    private(set) var phase: LoadPhase = .loading(.init(message: AccountsViewModel.loadingMessage))
    private(set) var banner: AccountsViewState.Banner?
    private(set) var monzoGuidanceVisible = false
    private(set) var busyProviders: Set<ProviderID> = []
    private(set) var isImporting = false
    private(set) var trading212Form: AccountsViewState.Trading212Form?
    private(set) var disconnectTarget: ProviderID?
    /// Live mode: the Monzo sign-in URL. The glue opens it in Safari.
    private(set) var consentURL: URL?
    /// True after the sync loop gave up (5 minutes). The "Import now" button stays.
    private(set) var syncTimedOut = false
    /// Number of sync attempts the loop made. For tests.
    private(set) var syncAttempts = 0

    @ObservationIgnored private var syncTask: Task<Void, Never>?
    @ObservationIgnored private var syncGeneration = 0
    @ObservationIgnored private var bannerTask: Task<Void, Never>?
    @ObservationIgnored var onClose: @MainActor () -> Void = {}
    /// Called after any change to connections, so the Money tab can reload.
    @ObservationIgnored var onConnectionsChanged: @MainActor () -> Void = {}

    init(client: any LifelineClient, sleep: @escaping Sleeper = { try await Task.sleep(for: $0) }) {
        self.client = client
        self.sleep = sleep
    }

    var state: AccountsViewState {
        var state = Self.makeState(
            connections: connections, phase: phase, busy: busyProviders, monzoGuidanceVisible: monzoGuidanceVisible,
            isImporting: isImporting, syncTimedOut: syncTimedOut
        )
        state.banner = banner
        state.trading212Form = trading212Form
        if let disconnectTarget { state.disconnectPrompt = Self.prompt(for: disconnectTarget) }
        return state
    }

    var actions: AccountsActions {
        AccountsActions(
            onConnectMonzo: { [weak self] in Task { await self?.connectMonzo() } },
            onConnectTrading212: { [weak self] in
                self?.trading212Form = .init(isSubmitting: false, errorText: nil, guidance: Self.trading212Guidance)
            },
            onSubmitTrading212: { [weak self] key, secret in Task { await self?.submitTrading212(apiKey: key, apiSecret: secret) } },
            onCancelTrading212: { [weak self] in self?.trading212Form = nil },
            onImportNow: { [weak self] in Task { await self?.importNow() } },
            onRequestDisconnect: { [weak self] id in self?.disconnectTarget = ProviderID(rawValue: id) },
            onConfirmDisconnect: { [weak self] in Task { await self?.confirmDisconnect() } },
            onCancelDisconnect: { [weak self] in self?.disconnectTarget = nil },
            onDismissBanner: { [weak self] in self?.dismissBanner() },
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    // MARK: Loading

    func load() async {
        if connections == nil { phase = .loading(.init(message: Self.loadingMessage)) }
        do {
            connections = try await client.listConnections()
            phase = .ready
            startSyncIfNeeded()
        } catch {
            if connections == nil {
                phase = .failed(.from(APIError.map(error)))
            } else {
                show(.error, APIError.map(error).userMessage)
            }
        }
    }

    // MARK: Monzo

    func connectMonzo() async {
        busyProviders.insert(.monzo)
        defer { busyProviders.remove(.monzo) }
        do {
            let link = try await client.bankAuthLink()
            if client.kind == .mock {
                // Sample mode has no emailed link: connect with a placeholder token and carry on.
                _ = try await client.connectMonzoToken("sample")
                await refreshAfterChange()
                show(.success, "Monzo connected (sample data).")
            } else if let url = URL(string: link.url) {
                monzoGuidanceVisible = true
                consentURL = url
            } else {
                show(.error, "Something went wrong. Try again.")
            }
        } catch {
            show(.error, Self.monzoMessage(APIError.map(error)))
        }
    }

    /// The glue calls this after it opened the URL, so the same link is not opened twice.
    func consentURLOpened() { consentURL = nil }

    /// Handles the `lifeline://connected` return from Safari.
    func handle(_ result: ConnectionReturn) async {
        switch result {
        case .connected:
            monzoGuidanceVisible = false
            await refreshAfterChange()
            show(.success, "Monzo connected.")
        case let .failed(code):
            monzoGuidanceVisible = false
            show(.error, ConnectionReturn.message(for: code))
        }
    }

    // MARK: History import

    /// Starts the retry loop when Monzo is connected but its history is not imported. No-op if already running.
    func startSyncIfNeeded() {
        guard syncTask == nil, Self.monzoNeedsSync(connections) else { return }
        syncTimedOut = false
        syncGeneration += 1
        let generation = syncGeneration
        syncTask = Task { [weak self] in await self?.runSyncLoop(generation: generation) }
    }

    /// Waits for the running retry loop to end. For tests.
    func waitForSync() async { await syncTask?.value }

    /// Stops the loop. The screen calls this when it disappears.
    func stopSync() {
        syncTask?.cancel()
        syncTask = nil
        syncGeneration += 1
    }

    private func runSyncLoop(generation: Int) async {
        var waited: Duration = .zero
        while !Task.isCancelled, waited < Self.syncLimit {
            do { try await sleep(Self.syncInterval) } catch { break }
            waited += Self.syncInterval
            if Task.isCancelled { break }
            guard await syncOnce() else { break }
        }
        guard generation == syncGeneration else { return }
        if waited >= Self.syncLimit, Self.monzoNeedsSync(connections) { syncTimedOut = true }
        syncTask = nil
    }

    /// One import attempt. Returns true when the loop should keep going.
    private func syncOnce() async -> Bool {
        syncAttempts += 1
        do {
            let status = try await client.syncMonzo()
            if status.synced {
                await refreshAfterChange()
                show(.success, "Your Monzo history is imported.")
                return false
            }
            applyHistory(status)
            return Self.isApprovalPending(status)
        } catch {
            let apiError = APIError.map(error)
            if case let .server(_, code, _, _) = apiError, code == "not_connected" {
                await load()
            } else {
                show(.error, Self.monzoMessage(apiError))
            }
            return false
        }
    }

    /// The "Import now" button. One attempt now, then the loop resumes if Monzo still waits for approval.
    func importNow() async {
        guard !isImporting else { return }
        isImporting = true
        stopSync()
        defer { isImporting = false }
        syncTimedOut = false
        if await syncOnce() { startSyncIfNeeded() }
    }

    private func applyHistory(_ status: HistoryStatus) {
        guard var list = connections?.providers, let index = list.firstIndex(where: { $0.provider == .monzo }) else { return }
        list[index].history = status
        connections = ConnectionsResponse(providers: list)
    }

    // MARK: Trading212

    func submitTrading212(apiKey: String, apiSecret: String) async {
        let key = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        let secret = apiSecret.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !key.isEmpty, !secret.isEmpty else {
            trading212Form?.errorText = "Enter both the key and the secret."
            return
        }
        trading212Form?.isSubmitting = true
        trading212Form?.errorText = nil
        do {
            _ = try await client.connectTrading212(apiKey: key, apiSecret: secret)
            trading212Form = nil
            await refreshAfterChange()
            show(.success, "Trading212 connected.")
        } catch {
            trading212Form?.isSubmitting = false
            trading212Form?.errorText = Self.trading212Message(APIError.map(error))
        }
    }

    // MARK: Disconnect

    func confirmDisconnect() async {
        guard let provider = disconnectTarget else { return }
        disconnectTarget = nil
        busyProviders.insert(provider)
        defer { busyProviders.remove(provider) }
        do {
            connections = try await client.disconnect(provider)
            if provider == .monzo { stopSync(); monzoGuidanceVisible = false }
            show(.info, "\(provider.displayName) disconnected.")
            onConnectionsChanged()
        } catch {
            show(.error, APIError.map(error).userMessage)
        }
    }

    // MARK: Helpers

    private func refreshAfterChange() async {
        do {
            connections = try await client.listConnections()
            phase = .ready
        } catch {
            show(.error, APIError.map(error).userMessage)
        }
        onConnectionsChanged()
        startSyncIfNeeded()
    }

    func show(_ kind: AccountsViewState.BannerKind, _ text: String) {
        banner = .init(kind: kind, text: text)
        bannerTask?.cancel()
        bannerTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(5))
            guard !Task.isCancelled else { return }
            self?.banner = nil
        }
    }

    func dismissBanner() {
        bannerTask?.cancel()
        banner = nil
    }

    // MARK: Pure mapping (used by fixtures and tests)

    static func monzoNeedsSync(_ connections: ConnectionsResponse?) -> Bool {
        guard let monzo = connections?.providers.first(where: { $0.provider == .monzo }), monzo.connected else { return false }
        guard let history = monzo.history else { return false }
        return !history.synced && isApprovalPending(history)
    }

    /// True when Monzo refused the import because access is not approved yet (or no error is known yet).
    static func isApprovalPending(_ history: HistoryStatus) -> Bool {
        guard !history.synced else { return false }
        guard let error = history.lastError else { return true }
        return error == "auth" || error == "provider_auth"
    }

    static func prompt(for provider: ProviderID) -> AccountsViewState.DisconnectPrompt {
        switch provider {
        case .monzo:
            .init(providerID: provider.rawValue, title: "Disconnect Monzo?",
                  message: "This deletes the history we imported from Monzo. The Money tab goes back to sample data.",
                  confirmTitle: "Disconnect and delete")
        case .trading212:
            .init(providerID: provider.rawValue, title: "Disconnect Trading212?",
                  message: "We forget your key and secret. Your investments go back to sample data.",
                  confirmTitle: "Disconnect")
        }
    }

    static func monzoMessage(_ error: APIError) -> String {
        if case let .server(_, code, _, _) = error {
            switch code {
            case "provider_auth": return "Monzo has not approved access yet. Approve the request in your Monzo app, then try again."
            case "rate_limited": return "Monzo is busy. Try again in a minute."
            case "unavailable", "timeout", "bad_data": return "Monzo is not answering right now. Try again soon."
            case "not_configured", "offline": return "Monzo sign-in is not available on this server."
            default: break
            }
        }
        return error.userMessage
    }

    static func trading212Message(_ error: APIError) -> String {
        if case let .server(_, code, _, _) = error {
            switch code {
            case "provider_auth": return "Key rejected. Check both the key and the secret."
            case "rate_limited": return "Trading212 is busy. Try again in a minute."
            case "unavailable", "timeout", "bad_data", "bad_gateway", "gateway_timeout":
                return "Trading212 is not answering right now. Try again soon."
            case "offline", "not_configured": return "Live connections are switched off on this server."
            default: break
            }
        }
        return error.userMessage
    }

    static func makeState(
        connections: ConnectionsResponse?,
        phase: LoadPhase,
        busy: Set<ProviderID> = [],
        monzoGuidanceVisible: Bool = false,
        isImporting: Bool = false,
        syncTimedOut: Bool = false
    ) -> AccountsViewState {
        let list = connections?.providers ?? []
        let rows = ProviderID.allCases.map { id -> AccountsViewState.Row in
            row(for: id, connection: list.first(where: { $0.provider.rawValue == id.rawValue }), isBusy: busy.contains(id))
        }
        let waiting = rows.first(where: { $0.id == ProviderID.monzo.rawValue })?.historyKind == .waitingForApproval
        let monzoConnected = list.first(where: { $0.provider == .monzo })?.connected == true
        let showsImport = monzoConnected && rows.first(where: { $0.id == ProviderID.monzo.rawValue })?.historyKind != .imported
        return AccountsViewState(
            phase: phase,
            rows: rows,
            banner: nil,
            monzoGuidance: monzoGuidanceVisible ? monzoGuidance : nil,
            approvalNote: waiting ? approvalMessage : nil,
            showsImportNow: showsImport,
            isImporting: isImporting,
            trading212Form: nil,
            disconnectPrompt: nil
        )
    }

    static func row(for id: ProviderID, connection: ProviderConnection?, isBusy: Bool) -> AccountsViewState.Row {
        let connected = connection?.connected == true
        let isSample = connected && connection?.dataStatus == .mock
        let status = !connected ? "Not connected" : (isSample ? "Sample data" : "Live")
        let hint = connection?.hint.map { (id == .monzo ? "Account " : "Key ") + $0 }
        var historyText: String?
        var historyKind: AccountsViewState.HistoryKind?
        if id == .monzo, connected, let history = connection?.history {
            if history.synced {
                historyKind = .imported
                historyText = history.oldest.map { "History imported back to \(FinanceMapping.dayText($0))" } ?? "History imported"
            } else if isApprovalPending(history) {
                historyKind = .waitingForApproval
                historyText = "Waiting for you to approve in the Monzo app"
            } else {
                historyKind = .problem
                historyText = "History not imported yet"
            }
        }
        return .init(
            id: id.rawValue,
            name: id.displayName,
            systemImage: id == .monzo ? "creditcard" : "chart.pie",
            subtitle: id == .monzo ? "Your spending, bills and subscriptions" : "Your investments and ISA",
            isConnected: connected,
            statusText: status,
            isSample: isSample,
            hintText: connected ? hint : nil,
            historyText: historyText,
            historyKind: historyKind,
            isBusy: isBusy
        )
    }
}
