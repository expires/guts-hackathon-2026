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
        /// Show the Money tab: a "you" challenge is scored on your own money, not on a life.
        case money
    }

    static var loadingMessage: String { L10n.tr("Loading your lives") }

    private let session: GameSession
    private(set) var lives: [LifeListItem] = []
    private(set) var challenges: [Challenge] = []
    /// The caller's progress on "you" challenges (scored on their own money data). Not disk cached: it is per user.
    private(set) var progress: [ChallengeProgress] = []
    private(set) var conceptsTotal = 0
    private(set) var phase: LoadPhase = .loading(.init(message: PlayViewModel.loadingMessage))
    @ObservationIgnored var onRoute: @MainActor (Route) -> Void = { _ in }

    init(session: GameSession) {
        self.session = session
    }

    var state: PlayViewState {
        Self.makeState(
            lives: lives, challenges: challenges, progress: progress, conceptsTotal: conceptsTotal, phase: phase,
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

    /// Challenges and concepts come from the disk cache first (ADR 0060), so Play shows content at once.
    /// Lives (your own, changing data) come from the network.
    func load() async {
        if challenges.isEmpty && lives.isEmpty { phase = .loading(.init(message: Self.loadingMessage)) }
        let client = session.client
        Task { [weak self] in
            try? await client.load(CachedOps.concepts) { concepts in self?.conceptsTotal = concepts.count }
        }
        try? await client.load(CachedOps.challenges) { [weak self] challenges in
            self?.challenges = challenges
            self?.phase = .ready
        }
        if let progress = try? await client.listChallengeProgress() { self.progress = progress }
        do {
            lives = try await client.listLives().lives
            phase = .ready
        } catch {
            if challenges.isEmpty { phase = .failed(.from(APIError.map(error))) }
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
    /// A "you" challenge has no life: it shows the Money tab instead (POST /v1/lives would return 404).
    func startChallenge(_ id: String) async {
        guard let challenge = challenges.first(where: { $0.id == id }) else { return }
        if challenge.scope == .you {
            onRoute(.money)
            return
        }
        let request = CreateLifeRequest(mode: .preset, startYear: challenge.startYear, presetId: challenge.characterId)
        if await session.startLife(request) { onRoute(.life) }
    }

    // MARK: Mapping (pure, used by fixtures and tests)

    static func makeState(
        lives: [LifeListItem],
        challenges: [Challenge],
        progress: [ChallengeProgress] = [],
        conceptsTotal: Int,
        phase: LoadPhase,
        current: Life?,
        isSampleData: Bool,
        isBusy: Bool
    ) -> PlayViewState {
        let ribbons = lives.reduce(0) { $0 + $1.ribbons }
        let unlocked = current?.conceptsUnlocked.count ?? 0
        return PlayViewState(
            phase: phase,
            lives: lives.map { item in
                PlayViewState.LifeRow(
                    id: item.id,
                    emoji: item.emoji,
                    name: item.name,
                    detail: item.alive ? L10n.tr("Age \(item.age) in \(String(item.year))") : L10n.tr("Died at \(item.age) in \(String(item.year))"),
                    isAlive: item.alive,
                    index: item.index,
                    netWorth: item.netWorth,
                    ribbons: item.ribbons,
                    isCurrent: item.id == current?.id
                )
            },
            challenges: challenges.map { challengeRow($0, progress: progress) },
            ribbonsTotal: ribbons,
            ribbonsText: ribbonsText(ribbons: ribbons, lives: lives.count),
            conceptsUnlocked: unlocked,
            conceptsTotal: conceptsTotal,
            conceptsText: L10n.tr("\(unlocked) of \(conceptsTotal) concepts collected"),
            continueText: current.flatMap { life in
                life.alive ? L10n.tr("Continue as \(life.character.name), age \(life.age)") : nil
            },
            isSampleData: isSampleData,
            isBusy: isBusy
        )
    }

    /// A life challenge shows its start year. A "you" challenge shows its progress on your own money.
    static func challengeRow(_ challenge: Challenge, progress: [ChallengeProgress]) -> PlayViewState.ChallengeRow {
        guard challenge.scope == .you else {
            return .init(id: challenge.id, emoji: challenge.emoji, title: challenge.title, description: challenge.description,
                         detail: L10n.tr("Starts in \(String(challenge.startYear))"))
        }
        let entry = progress.first { $0.challengeId == challenge.id && $0.lifeId == nil }
        let status: PlayViewState.ChallengeRow.Status? = switch entry?.status {
        case .won: .won
        case .lost: .lost
        case .inProgress: .inProgress
        case nil: nil
        }
        return .init(
            id: challenge.id, emoji: challenge.emoji, title: challenge.title, description: challenge.description,
            detail: entry?.detail ?? L10n.tr("Scored on your own money. Tap to see it."),
            isYou: true, status: status
        )
    }

    /// "4 ribbons across 3 lives", with singular forms as full sentences for translation.
    static func ribbonsText(ribbons: Int, lives: Int) -> String {
        switch (ribbons == 1, lives == 1) {
        case (true, true): L10n.tr("1 ribbon across 1 life")
        case (true, false): L10n.tr("1 ribbon across \(lives) lives")
        case (false, true): L10n.tr("\(ribbons) ribbons across 1 life")
        case (false, false): L10n.tr("\(ribbons) ribbons across \(lives) lives")
        }
    }
}
