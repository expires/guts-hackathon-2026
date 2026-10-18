import Foundation
import Observation

/// Collection of all concepts. Unlocked ones are highlighted. Every lesson opens for free.
@MainActor
@Observable
final class ConceptCollectionViewModel {
    private let client: any LifelineClient
    private let unlocked: Set<String>
    private(set) var concepts: [Concept] = []
    private(set) var phase: LoadPhase = .loading(.init(message: L10n.tr("Loading concepts")))
    /// Set when the player taps a concept. The glue presents the lesson.
    var selectedLesson: Lesson?
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(client: any LifelineClient, unlockedIDs: [String]) {
        self.client = client
        self.unlocked = Set(unlockedIDs)
    }

    var state: ConceptCollectionViewState {
        Self.makeState(concepts: concepts, unlocked: unlocked, phase: phase)
    }

    var actions: ConceptCollectionActions {
        ConceptCollectionActions(
            onSelect: { [weak self] id in
                self?.selectedLesson = self?.concepts.first { $0.id == id }?.lesson
            },
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    func load() async {
        phase = .loading(.init(message: L10n.tr("Loading concepts")))
        do {
            concepts = try await client.listConcepts()
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    static func makeState(concepts: [Concept], unlocked: Set<String>, phase: LoadPhase) -> ConceptCollectionViewState {
        let items = concepts.map {
            ConceptCollectionViewState.Item(
                id: $0.id,
                emoji: $0.emoji,
                title: $0.title,
                areaLabel: $0.area.rawValue.capitalized,
                summary: $0.summary,
                isUnlocked: unlocked.contains($0.id)
            )
        }
        return ConceptCollectionViewState(
            phase: phase,
            items: items,
            unlockedCount: items.filter(\.isUnlocked).count,
            totalCount: items.count
        )
    }
}
