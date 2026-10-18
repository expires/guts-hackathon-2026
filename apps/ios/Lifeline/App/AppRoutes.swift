import SwiftUI

/// Where onboarding opens (W6's `OnboardingScreen`).
enum OnboardingStart: String, Hashable, Identifiable, Sendable {
    var id: String { rawValue }

    /// Full flow from the welcome step (first launch, after sign-out or a demo reset).
    case welcome
    /// Straight to "Connect your money" (from Money home or the You tab).
    case connect
}

/// What the user asks Penny about (ADR 0031). The root turns it into W7's `PennyContext`.
struct PennyRoute: Identifiable, Hashable, Sendable {
    enum Screen: String, Hashable, Sendable {
        case money, nextMove, why, lifeEvent, life, testIt, other
    }

    var id = UUID()
    var screen: Screen = .other
    var nextMoveID: String?
    var lifeID: String?
    var eventID: String?
    /// Optional first question, sent at once when the chat opens.
    var question: String?
    /// Thread title for the new chat, from the context (e.g. "Safety fund, age 19").
    var title: String?

    init(
        screen: Screen = .other,
        nextMoveID: String? = nil,
        lifeID: String? = nil,
        eventID: String? = nil,
        question: String? = nil,
        title: String? = nil
    ) {
        self.screen = screen
        self.nextMoveID = nextMoveID
        self.lifeID = lifeID
        self.eventID = eventID
        self.question = question
        self.title = title
    }

    /// The contract `ChatContext` for `ChatRequest.context`.
    var chatContext: ChatContext {
        let screen: ChatContext.ScreenPayload = switch self.screen {
        case .money: .money
        case .nextMove: .nextMove
        case .why: .why
        case .lifeEvent: .lifeEvent
        case .life: .life
        case .testIt: .testIt
        case .other: .other
        }
        return ChatContext(nextMoveId: nextMoveID, lifeId: lifeID, eventId: eventID, screen: screen, title: title)
    }
}

/// A room to join from a deep link (`lifeline://join/CODE`) or a call to `joinRoom(code:)`.
struct RoomJoinRoute: Identifiable, Hashable, Sendable {
    let code: String
    var id: String { code }
}

/// App-wide navigation actions. Read with `@Environment(\.appRoutes) private var routes`.
/// `RootScreen` installs the real closures. Previews and tests get `.noop`.
struct AppRoutes: Sendable {
    /// Opens the Ask Penny sheet over any screen.
    var askPenny: @MainActor @Sendable (PennyRoute) -> Void
    /// Opens onboarding at "Connect your money".
    var openConnectMoney: @MainActor @Sendable () -> Void
    /// Opens the full onboarding flow.
    var openOnboarding: @MainActor @Sendable () -> Void
    /// Opens account actions (W6's `AccountScreen`).
    var openAccount: @MainActor @Sendable () -> Void
    /// Opens the room join screen for a 6-character code.
    var joinRoom: @MainActor @Sendable (String) -> Void
    /// Switches the tab (closes the Penny sheet first if it is open).
    var selectTab: @MainActor @Sendable (AppTab) -> Void
    /// Opens the language screen (ADR 0063), for example from You > Change language.
    var changeLanguage: @MainActor @Sendable () -> Void
    /// Judge mode (ADR 0049): a fresh demo account on a new device id, then onboarding.
    var newPlayer: @MainActor @Sendable () -> Void
    /// Judge mode (ADR 0049): `POST /v1/me/reset` for this account, then onboarding.
    var resetDemo: @MainActor @Sendable () -> Void

    static let noop = AppRoutes(
        askPenny: { _ in },
        openConnectMoney: {},
        openOnboarding: {},
        openAccount: {},
        joinRoom: { _ in },
        selectTab: { _ in },
        changeLanguage: {},
        newPlayer: {},
        resetDemo: {}
    )

    /// Same as `askPenny(route)`.
    @MainActor
    func callAsFunction(_ route: PennyRoute) {
        askPenny(route)
    }
}

extension EnvironmentValues {
    @Entry var appRoutes: AppRoutes = .noop
    /// Bumped when the user's money data changes as a whole (onboarding finished, signed out).
    /// Screens reload with `.task(id: dataVersion)` or `.onChange(of: dataVersion)`.
    @Entry var appDataVersion: Int = 0
    /// The selected root tab. Full-screen covers inside a tab (e.g. Play solo) close when it changes away
    /// from their tab, so "Ask Penny" from a Life event shows the Penny tab, not the cover (V4 F4-1).
    @Entry var appSelectedTab: AppTab = .money
}

/// Root navigation state. Owned by `RootScreen`.
@MainActor
@Observable
final class AppRouter {
    enum Gate: Equatable {
        /// Waiting for `GET /v1/me`.
        case checking
        /// No finance data: onboarding replaces the tabs.
        case onboarding
        /// Tabs.
        case ready
    }

    var selection: AppTab = .launch
    var gate: Gate = .checking
    /// The current player's game session. Judge mode replaces it.
    private(set) var session: GameSession
    /// The Penny tab chat for the current player.
    private(set) var pennyModel: PennyTabModel
    /// Changes when the session is replaced. RootScreen uses it as the view identity.
    private(set) var sessionID = 0
    /// True while "New player" or "Reset demo" runs.
    private(set) var isResetting = false

    init(session: GameSession) {
        self.session = session
        self.pennyModel = PennyTabModel(client: session.client)
    }
    var penny: PennyRoute?
    var onboarding: OnboardingStart?
    var showsAccount = false
    /// The language screen (`routes.changeLanguage()`).
    var showsLanguage = false
    var join: RoomJoinRoute?
    /// See `EnvironmentValues.appDataVersion`.
    var dataVersion = 0

    /// Launch arguments: `-onboarding` forces the gate on, `-skipOnboarding` turns it off.
    static let forceOnboardingArgument = "-onboarding"
    static let skipOnboardingArgument = "-skipOnboarding"

    var routes: AppRoutes {
        AppRoutes(
            askPenny: { [weak self] route in self?.penny = route },
            openConnectMoney: { [weak self] in self?.onboarding = .connect },
            openOnboarding: { [weak self] in self?.onboarding = .welcome },
            openAccount: { [weak self] in self?.showsAccount = true },
            joinRoom: { [weak self] code in self?.join = RoomJoinRoute(code: code) },
            selectTab: { [weak self] tab in
                self?.penny = nil
                self?.selection = tab
            },
            changeLanguage: { [weak self] in
                self?.penny = nil
                self?.showsLanguage = true
            },
            newPlayer: { [weak self] in
                guard let self else { return }
                Task { await self.newPlayer() }
            },
            resetDemo: { [weak self] in
                guard let self else { return }
                Task { await self.resetDemo() }
            }
        )
    }

    /// Decides the onboarding gate from `GET /v1/me`: onboarding when `has_finance_data` is false.
    /// - A cached `Me` on disk decides at once (instant launch). The fresh value can still switch
    ///   the tabs to onboarding, never the other way round while onboarding is open.
    /// - No cached value: waits for the network, at most 5 s. A failure or timeout opens the tabs.
    /// When the tabs open, the launch prefetch starts (once).
    func checkGate(client: any LifelineClient, arguments: [String] = ProcessInfo.processInfo.arguments) async {
        if arguments.contains(Self.forceOnboardingArgument) {
            gate = .onboarding
            return
        }
        if arguments.contains(Self.skipOnboardingArgument) {
            openTabs(client: client)
            return
        }
        if let cached = await client.cached(CachedOps.me) {
            applyGate(hasData: cached.hasFinanceData, client: client)
            Task { try? await client.load(CachedOps.me) { [weak self] me in self?.applyGate(hasData: me.hasFinanceData, client: client) } }
            return
        }
        let hasData = await withTaskGroup(of: Bool?.self) { group in
            group.addTask {
                guard let me = try? await client.getMe() else { return nil }
                if let disk = client.diskCache {
                    await disk.setOwner(me.id)
                    await disk.write(me, key: CachedOps.me.key, scope: CachedOps.me.scope)
                }
                return me.hasFinanceData
            }
            group.addTask {
                try? await Task.sleep(for: .seconds(5))
                return nil
            }
            let first = await group.next() ?? nil
            group.cancelAll()
            return first
        }
        if hasData == false {
            gate = .onboarding
        } else {
            openTabs(client: client)
        }
    }

    private func applyGate(hasData: Bool, client: any LifelineClient) {
        if !hasData {
            if gate != .onboarding { gate = .onboarding }
        } else if gate == .checking {
            openTabs(client: client)
        }
    }

    private func openTabs(client: any LifelineClient) {
        gate = .ready
        prefetch(client: client)
    }

    private var didPrefetch = false

    /// Launch prefetch (ADR 0060), once per app session, after the gate opens the tabs:
    /// Me, Money home, profile, plan, habits, concepts, paths and challenges, in parallel.
    /// It fills the disk cache and the 20 s memory cache, so tab switches show content at once.
    func prefetch(client: any LifelineClient) {
        guard !didPrefetch else { return }
        didPrefetch = true
        Task.detached(priority: .utility) {
            await withTaskGroup(of: Void.self) { group in
                group.addTask { await client.refresh(CachedOps.me) }
                group.addTask { await client.refresh(CachedOps.financeHome) }
                group.addTask { await client.refresh(CachedOps.financeProfile) }
                group.addTask { await client.refresh(CachedOps.plan) }
                group.addTask { await client.refresh(CachedOps.habits) }
                group.addTask { await client.refresh(CachedOps.concepts) }
                group.addTask { await client.refresh(CachedOps.paths) }
                group.addTask { await client.refresh(CachedOps.challenges) }
                // Money home blocks (ADR 0070), so each shows from disk on the first open.
                group.addTask { await client.refresh(CachedOps.spending()) }
                group.addTask { await client.refresh(CachedOps.bills) }
                group.addTask { await client.refresh(CachedOps.subscriptions) }
                group.addTask { await client.refresh(CachedOps.budgets) }
                group.addTask { await client.refresh(CachedOps.goals) }
            }
        }
    }

    /// Onboarding finished (gate or sheet): land on Money with fresh data.
    func finishOnboarding(client: any LifelineClient) async {
        await client.clearResponseCache()
        dataVersion += 1
        onboarding = nil
        selection = .money
        didPrefetch = false
        openTabs(client: client)
    }

    /// Signed out or account deleted: back to the gate.
    func signedOut(client: any LifelineClient) async {
        showsAccount = false
        penny = nil
        await client.clearResponseCache()
        await client.diskCache?.clearUser()
        dataVersion += 1
        didPrefetch = false
        gate = .checking
        await checkGate(client: client)
    }

    // MARK: Judge mode (ADR 0049)

    /// New player: sign out, write a new device id, clear every cache, rebuild the client and the session
    /// (LiveClient reads `DeviceIdentity` once at init), new Penny chat, then onboarding.
    /// A `-demoDeviceID` launch argument still wins over the new id (DeviceIdentity precedence).
    func newPlayer(defaults: UserDefaults = .standard) async {
        guard !isResetting else { return }
        isResetting = true
        defer { isResetting = false }
        let old = session.client
        try? await old.signOut()
        await old.clearResponseCache()
        await old.diskCache?.clearUser()
        defaults.set(UUID().uuidString, forKey: DeviceIdentity.defaultsKey)
        defaults.removeObject(forKey: DeviceIdentity.debugOverrideKey)
        let client = old.kind == .mock ? ClientFactory.make(.mock) : ClientFactory.make(.live)
        replaceSession(GameSession(client: client))
    }

    /// Reset demo: clear this account's lives, plan, guesses and money on the server, clear caches,
    /// new session and Penny chat, then onboarding. On a server error the session stays and the error shows.
    func resetDemo() async {
        guard !isResetting else { return }
        isResetting = true
        defer { isResetting = false }
        let client = session.client
        do {
            _ = try await client.resetDemo()
        } catch {
            session.errorMessage = APIError.map(error).userMessage
            return
        }
        await client.clearResponseCache()
        await client.diskCache?.clearUser()
        replaceSession(GameSession(client: client))
    }

    private func replaceSession(_ new: GameSession) {
        session = new
        pennyModel = PennyTabModel(client: new.client)
        sessionID += 1
        dataVersion += 1
        didPrefetch = false
        penny = nil
        onboarding = nil
        showsAccount = false
        join = nil
        selection = .money
        gate = .onboarding
    }

    /// `lifeline://join/CODE`. Returns true when the URL was a join link.
    @discardableResult
    func handle(url: URL) -> Bool {
        guard let code = RoomLink.code(from: url) else { return false }
        penny = nil
        join = RoomJoinRoute(code: code)
        return true
    }
}
