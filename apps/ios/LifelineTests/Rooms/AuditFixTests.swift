import Foundation
import Testing
@testable import Lifeline

/// UX map audit fixes: "you" challenges, the Play solo error alert, the room Start rule,
/// the Same Life start error and the results Reconnect button.
@MainActor
@Suite("Audit fixes: Play and rooms")
struct AuditFixTests {
    // MARK: 1. "you" challenges

    static let youChallenge = Challenge(
        id: "safety-fund-1m", title: "1 month safety fund", emoji: "🛟",
        description: "Save one month of your regular costs.", characterId: "you", startYear: 2026,
        goal: .init(), scope: .you
    )

    @Test func youChallengeShowsMoneyTabAndStartsNoLife() async {
        var data = MockData.contract
        data.challenges.append(Self.youChallenge)
        let session = GameSession(client: MockClient(data: data))
        let model = PlayViewModel(session: session)
        await model.load()
        var route: PlayViewModel.Route?
        model.onRoute = { route = $0 }
        await model.startChallenge("safety-fund-1m")
        #expect(route == .money)
        #expect(session.life == nil)
        #expect(session.errorMessage == nil)
        let row = model.state.challenges.first { $0.id == "safety-fund-1m" }
        #expect(row?.isYou == true)
        #expect(row?.status == nil)
        #expect(row?.detail == "Scored on your own money. Tap to see it.")
    }

    @Test func youChallengeRowShowsProgress() {
        let progress = [
            ChallengeProgress(challengeId: "safety-fund-1m", status: .inProgress, detail: "40% of a month saved."),
            ChallengeProgress(challengeId: "home-by-30", lifeId: "lf_1", status: .won, detail: "Life detail"),
        ]
        let life = ContractExamples.challenges[0]
        let state = PlayViewModel.makeState(
            lives: [], challenges: [Self.youChallenge, life], progress: progress, conceptsTotal: 0,
            phase: .ready, current: nil, isSampleData: false, isBusy: false
        )
        #expect(state.challenges[0].status == .inProgress)
        #expect(state.challenges[0].status?.text == "In progress")
        #expect(state.challenges[0].detail == "40% of a month saved.")
        // A life challenge keeps its start year and no status.
        #expect(!state.challenges[1].isYou)
        #expect(state.challenges[1].status == nil)
        #expect(state.challenges[1].detail == "Starts in \(life.startYear)")
        let won = PlayViewModel.challengeRow(Self.youChallenge, progress: [.init(challengeId: "safety-fund-1m", status: .won, detail: "Done.")])
        #expect(won.status == .won)
        let lost = PlayViewModel.challengeRow(Self.youChallenge, progress: [.init(challengeId: "safety-fund-1m", status: .lost)])
        #expect(lost.status == .lost)
    }

    // MARK: 2. One error alert at a time

    @Test func onlyTopHostShowsSessionError() {
        let hosts = SessionErrorHosts()
        #expect(hosts.isTop(nil))
        let solo = UUID()
        let event = UUID()
        hosts.push(solo)
        #expect(!hosts.isTop(nil))
        #expect(hosts.isTop(solo))
        hosts.push(event)
        #expect(hosts.isTop(event))
        #expect(!hosts.isTop(solo))
        hosts.pop(event)
        #expect(hosts.isTop(solo))
        hosts.pop(solo)
        #expect(hosts.isTop(nil))
    }

    // MARK: 3. Start rule matches the server

    @Test func startNeedsEveryPlayerReady() {
        let waiting = RoomFlowFixtures.lobbyHost
        #expect(!waiting.canStart)
        #expect(waiting.startTitle == "Waiting for 1 to get ready")

        var room = RoomFlowFixtures.quizRoom
        room.players[3].ready = true
        let ready = RoomFlowFixtures.lobby(room: room)
        #expect(ready.canStart)
        #expect(ready.startTitle == "Start with 4 players")

        // An away player still has a seat: the server waits for them too.
        room.players[3].ready = false
        room.players[3].connected = false
        #expect(!RoomFlowFixtures.lobby(room: room).canStart)

        // The host alone cannot start.
        room.players = [room.players[0]]
        let alone = RoomFlowFixtures.lobby(room: room)
        #expect(!alone.canStart)
        #expect(alone.startTitle == "Waiting for players")
    }

    // MARK: 4 and 5. Same Life start error, results Reconnect

    private func failingClient() -> LiveClient {
        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [FailingURLProtocol.self]
        return LiveClient(
            baseURL: URL(string: "https://audit.invalid")!, deviceID: "audit-test",
            session: URLSession(configuration: config),
            tokenStore: TokenStore(service: "com.lifeline.tests.audit", account: "audit"), diskCache: nil
        )
    }

    @Test func sameLifeStartErrorShowsOnLiveScreenWithRetry() async throws {
        FailingURLProtocol.reset()
        let game = GameSession(client: failingClient())
        let transport = FakeRoomTransport(room: RoomTestData.room(status: .playing))
        let session = RoomSession(transport: transport, retryDelays: [], pingInterval: nil)
        let model = RoomFlowViewModel(game: game, session: session, play: MockPlayService())
        await session.open(room: transport.room, name: "Ash")
        let socket = try #require(transport.latest)
        socket.push(RoomTestData.welcome(room: transport.room))
        #expect(await eventually { session.room != nil })

        await model.startMyLife(in: transport.room)
        #expect(model.liveState?.startError != nil)
        // The live banner shows it; no second alert at the root.
        #expect(game.errorMessage == nil)

        let before = FailingURLProtocol.count
        model.liveActions.onRetryStart()
        #expect(await eventually { FailingURLProtocol.count > before && !game.isBusy })
        #expect(await eventually { model.liveState?.startError != nil })
    }

    @Test func resultsReconnectReconnects() async throws {
        let transport = FakeRoomTransport(room: RoomTestData.room(status: .finished))
        let session = RoomSession(transport: transport, retryDelays: [], pingInterval: nil)
        let model = RoomFlowViewModel(game: GameSession(client: MockClient()), session: session, play: MockPlayService())
        await session.open(room: transport.room, name: "Ash")
        #expect(await eventually { transport.connections.count == 1 })
        model.resultActions.onReconnect()
        #expect(await eventually { transport.connections.count == 2 })
    }
}

/// Fails every request at once, so a `LiveClient` call fails without the network.
final class FailingURLProtocol: URLProtocol, @unchecked Sendable {
    nonisolated(unsafe) private static var _count = 0
    private static let lock = NSLock()
    static var count: Int { lock.withLock { _count } }
    static func reset() { lock.withLock { _count = 0 } }

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        Self.lock.withLock { Self._count += 1 }
        client?.urlProtocol(self, didFailWithError: URLError(.notConnectedToInternet))
    }
    override func stopLoading() {}
}
