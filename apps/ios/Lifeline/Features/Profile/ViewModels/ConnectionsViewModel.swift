import Foundation
import Observation

/// The backend calls the connect step needs, as closures (tests pass their own).
struct ConnectionsAPI: Sendable {
    var profileStats: @Sendable () async throws -> ProfileStats
    var connections: @Sendable () async throws -> ConnectionsResponse
    var connectTrading212: @Sendable (_ key: String, _ secret: String) async throws -> Void
    var disconnect: @Sendable (_ provider: String) async throws -> Void
    var importStatement: @Sendable (_ file: Data, _ fileName: String, _ provider: String?) async throws -> Void
    var monzo: MonzoConnectFlow.API

    static func from(client: any LifelineClient) -> ConnectionsAPI {
        ConnectionsAPI(
            profileStats: { try await client.profileStats() },
            connections: { try await client.listConnections() },
            connectTrading212: { key, secret in _ = try await client.connectTrading212(key: key, secret: secret) },
            disconnect: { provider in _ = try await client.disconnectProvider(provider) },
            importStatement: { file, name, provider in _ = try await client.importStatement(file: file, fileName: name, provider: provider) },
            monzo: .init(
                bankAuthLink: { provider in try await client.bankAuthLink(provider: provider) },
                monzoConnected: { try await client.listConnections().providers.first { $0.provider == .monzo }?.connected ?? false },
                syncMonzo: { try await client.syncMonzo() }
            )
        )
    }
}

/// The connect step: Monzo, Trading 212, Upload a statement, Enter your numbers, each with its status.
/// One screen for both entry points. The Monzo sign-in is the same `MonzoConnectFlow` onboarding uses.
@MainActor
@Observable
final class ConnectionsViewModel {
    private let api: ConnectionsAPI
    private let monzo: MonzoConnectFlow
    private(set) var state: ConnectionsViewState
    private var stats: ProfileStats?
    private var providers: [ProviderConnection] = []

    // Platform and caller hooks, set by the glue.
    /// Opens Monzo's sign-in in Safari.
    @ObservationIgnored var openInSafari: (@MainActor (URL) -> Void)? {
        didSet { monzo.openInSafari = openInSafari }
    }
    /// Shows the file picker. The glue calls `importStatement(data:fileName:)`.
    @ObservationIgnored var pickStatement: @MainActor () -> Void = {}
    /// Opens "Enter your numbers".
    @ObservationIgnored var enterNumbers: @MainActor () -> Void = {}
    @ObservationIgnored var onContinue: @MainActor () -> Void = {}
    @ObservationIgnored var onClose: @MainActor () -> Void = {}
    /// Something was connected, changed or disconnected. The stats page reloads.
    @ObservationIgnored var onChanged: @MainActor () -> Void = {}

    static let maxStatementBytes = 5 * 1024 * 1024

    init(api: ConnectionsAPI, continueTitle: String? = nil, highlighted: ConnectKind? = nil) {
        self.api = api
        self.monzo = MonzoConnectFlow(api: api.monzo)
        var state = ConnectionsViewState()
        state.continueTitle = continueTitle
        state.highlighted = highlighted
        self.state = state
        monzo.onWaitChange = { [weak self] wait in self?.state.monzoWait = wait }
        monzo.onUnavailable = { [weak self] in
            self?.state.errorMessage = L10n.tr("Monzo is unavailable right now. Upload a statement or enter your numbers.")
        }
        monzo.onError = { [weak self] message in self?.state.errorMessage = message }
        monzo.onApproved = { [weak self] _ in
            guard let self else { return }
            await refresh()
            state.notice = L10n.tr("Monzo is connected.")
            print("DBG notice set", ObjectIdentifier(self))
            onChanged()
        }
    }

    var actions: ConnectionsActions {
        ConnectionsActions(
            onConnect: { [weak self] kind in Task { await self?.connect(kind) } },
            onDisconnect: { [weak self] kind in self?.requestDisconnect(kind) },
            onConfirmDisconnect: { [weak self] in Task { await self?.confirmDisconnect() } },
            onCancelDisconnect: { [weak self] in self?.state.pendingDisconnect = nil },
            onContinue: { [weak self] in self?.onContinue() },
            onClose: { [weak self] in self?.onClose() },
            onRetry: { [weak self] in Task { await self?.load() } },
            onDismissError: { [weak self] in self?.state.errorMessage = nil },
            onSubmitTrading212: { [weak self] key, secret in Task { await self?.connectTrading212(key: key, secret: secret) } },
            onCloseTrading212: { [weak self] in self?.state.trading212 = .init() },
            onMonzoReopen: { [weak self] in self?.monzo.reopenSafari() },
            onMonzoCancel: { [weak self] in self?.monzo.cancel() },
            onMonzoRetry: { [weak self] in self?.monzo.retry() }
        )
    }

    // MARK: Loading

    func load() async {
        if stats == nil { state.phase = .loading(.init(message: L10n.tr("Checking your connections"))) }
        await refresh()
    }

    /// Reads the profile stats connections and `GET /v1/connections`. Either one is enough to show the rows.
    func refresh() async {
        async let statsResult = try? api.profileStats()
        async let connectionsResult = try? api.connections()
        let (newStats, newConnections) = await (statsResult, connectionsResult)
        if let newStats { stats = newStats }
        if let newConnections { providers = newConnections.providers }
        guard stats != nil || newConnections != nil else {
            state.phase = .failed(.from(APIError.connectionsUnavailable))
            return
        }
        state.rows = Self.makeRows(stats: stats, providers: providers)
        state.sampleNote = Self.sampleNote(stats: stats)
        state.phase = .ready
    }

    // MARK: Actions

    func connect(_ kind: ConnectKind) async {
        state.errorMessage = nil
        print("DBG connect clears notice")
        state.notice = nil
        switch kind {
        case .monzo:
            state.isBusy = true
            defer { state.isBusy = false }
            await monzo.start()
        case .trading212: state.trading212 = .init(isPresented: true)
        case .statement: pickStatement()
        case .manual: enterNumbers()
        }
    }

    /// Trading 212: the server checks the key with Trading 212 before it stores anything.
    func connectTrading212(key: String, secret: String) async {
        let key = key.trimmingCharacters(in: .whitespacesAndNewlines)
        let secret = secret.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !key.isEmpty, !secret.isEmpty else {
            state.trading212.errorMessage = L10n.tr("Enter both the key and the secret.")
            return
        }
        state.trading212.isBusy = true
        state.trading212.errorMessage = nil
        do {
            try await api.connectTrading212(key, secret)
            state.trading212 = .init()
            await refresh()
            state.notice = L10n.tr("Trading 212 is connected.")
            onChanged()
        } catch {
            state.trading212.isBusy = false
            let mapped = APIError.map(error)
            if case let .server(status, code, _, _) = mapped, status == 503 || status == 501 || code == "offline" {
                state.trading212 = .init()
                state.errorMessage = L10n.tr("Trading 212 is unavailable right now. Upload a statement or enter your numbers.")
            } else {
                state.trading212.errorMessage = mapped.userMessage
            }
        }
    }

    func importStatement(data: Data, fileName: String) async {
        guard data.count <= Self.maxStatementBytes else {
            state.errorMessage = L10n.tr("This file is larger than 5 MB. Export a shorter period and try again.")
            return
        }
        state.isBusy = true
        state.errorMessage = nil
        defer { state.isBusy = false }
        do {
            try await api.importStatement(data, fileName, fileName.lowercased().hasSuffix(".pdf") ? "pdf" : nil)
            await refresh()
            state.notice = L10n.tr("Your statement is added.")
            onChanged()
        } catch {
            state.errorMessage = APIError.map(error).userMessage
        }
    }

    /// Typed numbers were saved elsewhere (the onboarding form): reload.
    func numbersSaved() async {
        await refresh()
        state.notice = L10n.tr("Your numbers are saved.")
        onChanged()
    }

    func requestDisconnect(_ kind: ConnectKind) {
        guard kind.provider != nil else { return }
        state.pendingDisconnect = kind
    }

    func confirmDisconnect() async {
        guard let kind = state.pendingDisconnect, let provider = kind.provider else { return }
        state.pendingDisconnect = nil
        state.isBusy = true
        defer { state.isBusy = false }
        do {
            try await api.disconnect(provider)
            await refresh()
            state.notice = L10n.tr("\(kind.title) is disconnected.")
            onChanged()
        } catch {
            state.errorMessage = APIError.map(error).userMessage
        }
    }

    /// The app came back to the front: check for a Monzo connection at once.
    func recheckMonzo() { monzo.recheck() }
    /// `lifeline://connected?...` (Monzo's redirect).
    func handleConnectedURL(_ url: URL) { monzo.handleConnectedURL(url) }
    var monzoTask: Task<Void, Never>? { monzo.task }
    var monzoFlow: MonzoConnectFlow { monzo }

    // MARK: Pure mapping

    static func makeRows(stats: ProfileStats?, providers: [ProviderConnection]) -> [ConnectionsViewState.Row] {
        ConnectKind.allCases.map { kind in
            let conn = stats?.connections.first { $0.id.rawValue == kind.rawValue }
            let provider = providers.first { $0.provider.rawValue == kind.provider }
            let connected = conn?.connected ?? provider?.connected ?? false
            let badge: String? = switch (kind, conn?.dataStatus) {
            case (.monzo, .some(.live)), (.trading212, .some(.live)): L10n.tr("Live")
            case (.monzo, .some(.cached)), (.trading212, .some(.cached)): L10n.tr("Saved copy")
            default: nil
            }
            return .init(
                kind: kind,
                title: kind.title,
                subtitle: subtitle(kind),
                isConnected: connected,
                statusText: connected ? L10n.tr("Connected") : L10n.tr("Not connected"),
                detail: connected ? conn?.provides : nil,
                badge: connected ? badge : nil,
                connectTitle: connectTitle(kind, connected: connected),
                canDisconnect: connected && kind.provider != nil
            )
        }
    }

    static func subtitle(_ kind: ConnectKind) -> String {
        switch kind {
        case .monzo: L10n.tr("Sign in with Monzo. We only read.")
        case .trading212: L10n.tr("Add your investments with an API key.")
        case .statement: L10n.tr("Monzo or Revolut CSV, or a PDF. Max 5 MB.")
        case .manual: L10n.tr("Takes about 2 minutes")
        }
    }

    static func connectTitle(_ kind: ConnectKind, connected: Bool) -> String {
        switch (kind, connected) {
        case (.monzo, false): L10n.tr("Connect Monzo")
        case (.monzo, true): L10n.tr("Connect again")
        case (.trading212, false): L10n.tr("Connect Trading 212")
        case (.trading212, true): L10n.tr("Use a new key")
        case (.statement, false): L10n.tr("Upload a statement")
        case (.statement, true): L10n.tr("Upload another")
        case (.manual, false): L10n.tr("Enter your numbers")
        case (.manual, true): L10n.tr("Change your numbers")
        }
    }

    static func sampleNote(stats: ProfileStats?) -> String? {
        guard stats?.connections.first(where: { $0.id == .sample })?.connected == true else { return nil }
        return L10n.tr("You are using Sample data. Connecting your own money replaces it.")
    }
}
