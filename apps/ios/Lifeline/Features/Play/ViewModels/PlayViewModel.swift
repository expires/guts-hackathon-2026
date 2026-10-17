import Foundation
import Observation

/// Loads `GET /v1/lives`, `GET /v1/challenges` and `GET /v1/concepts` for the Play tab.
@MainActor
@Observable
final class PlayViewModel {
    enum Route: Equatable {
        /// Show the Life tab (after a life opened or started, or to choose a character).
        case life
        case rooms
        case concepts
    }

    static let loadingMessage = "Loading your lives"

    private let session: GameSession
    private(set) var lives: [LifeListItem] = []
    private(set) var challenges: [Challenge] = []
    private(set) var conceptsTotal = 0
    private(set) var phase: LoadPhase = .loading(.init(message: PlayViewModel.loadingMessage))
    @ObservationIgnored var onRoute: @MainActor (Route) -> Void = { _ in }

    init(session: GameSession) {
        self.session = session
    }

    var state: PlayViewState {
        Self.makeState(
            lives: lives, challenges: challenges, conceptsTotal: conceptsTotal, phase: phase,
            current: session.life, isSampleData: session.usesSampleData, isBusy: session.isBusy
        )
    }

    var actions: PlayActions {
        PlayActions(
            onPlay: { [weak self] in self?.onRoute(.life) },
            onOpenLife: { [weak self] id in Task { await self?.openLife(id) } },
            onStartChallenge: { [weak self] id in Task { await self?.startChallenge(id) } },
            onOpenRooms: { [weak self] in self?.onRoute(.rooms) },
            onOpenConcepts: { [weak self] in self?.onRoute(.concepts) },
            onRetry: { [weak self] in Task { await self?.load() } }
        )
    }

    func load() async {
        phase = .loading(.init(message: Self.loadingMessage))
        let client = session.client
        do {
            async let lives = client.listLives()
            async let challenges = client.listChallenges()
            async let concepts = client.listConcepts()
            self.lives = try await lives.lives
            self.challenges = (try? await challenges) ?? []
            conceptsTotal = (try? await concepts)?.count ?? 0
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    func openLife(_ id: String) async {
        if session.life?.id == id {
            onRoute(.life)
            return
        }
        if await session.openLife(id: id) { onRoute(.life) }
    }

    /// Starts the challenge's preset character in its start year.
    func startChallenge(_ id: String) async {
        guard let challenge = challenges.first(where: { $0.id == id }) else { return }
        let request = CreateLifeRequest(mode: .preset, startYear: challenge.startYear, presetId: challenge.characterId)
        if await session.startLife(request) { onRoute(.life) }
    }

    // MARK: Mapping (pure, used by fixtures and tests)

    static func makeState(
        lives: [LifeListItem],
        challenges: [Challenge],
        conceptsTotal: Int,
        phase: LoadPhase,
        current: Life?,
        isSampleData: Bool,
        isBusy: Bool
    ) -> PlayViewState {
        let ribbons = lives.reduce(0) { $0 + $1.ribbons }
        let unlocked = current?.conceptsUnlocked.count ?? 0
        let lifeWord = lives.count == 1 ? "life" : "lives"
        return PlayViewState(
            phase: phase,
            lives: lives.map { item in
                PlayViewState.LifeRow(
                    id: item.id,
                    emoji: item.emoji,
                    name: item.name,
                    detail: item.alive ? "Age \(item.age) in \(item.year)" : "Died at \(item.age) in \(item.year)",
                    isAlive: item.alive,
                    index: item.index,
                    netWorth: item.netWorth,
                    ribbons: item.ribbons,
                    isCurrent: item.id == current?.id
                )
            },
            challenges: challenges.map {
                .init(id: $0.id, emoji: $0.emoji, title: $0.title, description: $0.description, detail: "Starts in \($0.startYear)")
            },
            ribbonsTotal: ribbons,
            ribbonsText: "\(ribbons == 1 ? "1 ribbon" : "\(ribbons) ribbons") across \(lives.count) \(lifeWord)",
            conceptsUnlocked: unlocked,
            conceptsTotal: conceptsTotal,
            conceptsText: "\(unlocked) of \(conceptsTotal) concepts collected",
            continueText: current.flatMap { life in
                life.alive ? "Continue as \(life.character.name), age \(life.age)" : nil
            },
            isSampleData: isSampleData,
            isBusy: isBusy
        )
    }
}
