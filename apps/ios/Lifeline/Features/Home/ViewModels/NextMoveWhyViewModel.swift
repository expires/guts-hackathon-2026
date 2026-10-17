import Foundation
import Observation

/// "Why?" for one move. Evidence comes from the move. The lesson comes from `GET /v1/concepts`.
/// When the lesson has no `personal` sentence, the matching `PersonalFact` from
/// `GET /v1/finance/profile` fills it (same concept id; every number comes from its `facts`).
@MainActor
@Observable
final class NextMoveWhyViewModel {
    static let loadingMessage = "Loading the lesson"

    private let client: any LifelineClient
    let move: Move
    private let isSampleData: Bool
    private(set) var lesson: Lesson?
    private(set) var lessonPhase: LoadPhase = .loading(.init(message: NextMoveWhyViewModel.loadingMessage))
    /// Set by "Open the lesson". The glue presents `LessonScreen` and clears it.
    var presentedLesson: Lesson?
    /// The profile character from `GET /v1/finance/profile`. The Decision screen needs it.
    private(set) var character: CharacterSpec?
    @ObservationIgnored var onOpenDecision: @MainActor () -> Void = {}
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(client: any LifelineClient, move: Move, isSampleData: Bool) {
        self.client = client
        self.move = move
        self.isSampleData = isSampleData
    }

    var state: NextMoveWhyViewState {
        var state = Self.makeState(move: move, lesson: lesson, lessonPhase: lessonPhase, isSampleData: isSampleData)
        state.hasDecisionDetail = character != nil && Self.hasDecisionDetail(move)
        return state
    }

    var actions: NextMoveWhyActions {
        NextMoveWhyActions(
            onOpenLesson: { [weak self] in
                guard let self, let lesson else { return }
                presentedLesson = lesson
            },
            onOpenDecision: { [weak self] in
                guard let self, character != nil, Self.hasDecisionDetail(move) else { return }
                onOpenDecision()
            },
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    /// Mortgage moves have a full decision screen (`POST /v1/decisions`).
    static func hasDecisionDetail(_ move: Move) -> Bool {
        move.kind == .fixMortgage || move.kind == .remortgage
    }

    func load() async {
        let profile = try? await client.financeProfile()
        character = profile?.character
        guard let conceptID = move.conceptId else {
            lessonPhase = .ready
            return
        }
        lessonPhase = .loading(.init(message: Self.loadingMessage))
        do {
            let concepts = try await client.listConcepts()
            guard var found = concepts.first(where: { $0.id == conceptID })?.lesson else {
                lesson = nil
                lessonPhase = .ready
                return
            }
            if found.personal == nil, let profile {
                found.personal = profile.personalFacts.first(where: { $0.conceptId == conceptID })?.text
            }
            lesson = found
            lessonPhase = .ready
        } catch {
            lessonPhase = .failed(.from(APIError.map(error)))
        }
    }

    // MARK: Mapping (pure, used by fixtures and tests)

    static func makeState(move: Move, lesson: Lesson?, lessonPhase: LoadPhase, isSampleData: Bool) -> NextMoveWhyViewState {
        NextMoveWhyViewState(
            action: move.action,
            headline: move.headline,
            confidenceLabel: move.confidenceLabel,
            evidence: move.evidence.enumerated().map { offset, point in
                .init(id: offset, text: point.text, source: point.source.map(StateMapping.sourceChip))
            },
            sources: move.sources.map(StateMapping.sourceChip),
            lessonPhase: lessonPhase,
            lesson: lesson.map { .init(title: $0.title, sentences: $0.sentences, personal: $0.personal) },
            isSampleData: isSampleData
        )
    }
}
