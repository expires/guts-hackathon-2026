import Foundation

struct ConceptCollectionViewState: Equatable, Sendable {
    struct Item: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String
        var title: String
        var areaLabel: String
        var summary: String
        var isUnlocked: Bool
    }

    var phase: LoadPhase
    var items: [Item]
    var unlockedCount: Int
    var totalCount: Int
}

struct ConceptCollectionActions {
    /// Opens the lesson. Lessons are never paywalled.
    var onSelect: @MainActor (String) -> Void = { _ in }
    var onRetry: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}
    /// Opens the Learn course (ADR 0068), where every concept is a lesson in order. Nil hides the button.
    var onOpenLearn: (@MainActor () -> Void)? = nil

    static var noop: Self { .init() }
}
