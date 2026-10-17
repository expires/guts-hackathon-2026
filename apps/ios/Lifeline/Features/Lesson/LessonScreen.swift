import SwiftUI

/// Glue: owns `LessonViewModel` and feeds `LessonView`.
struct LessonScreen: View {
    @State private var model: LessonViewModel
    @Environment(\.llPresentationMode) private var presentation
    private let onClose: @MainActor () -> Void
    private let onRewind: (@MainActor () -> Void)?

    /// - Parameters:
    ///   - session: the running game. Adds "Year · Age", the concept count and the "Mock data" badge. Optional.
    ///   - onRewind: opens Rewind. Nil hides "Rewind and try again".
    init(
        lesson: Lesson,
        isNewConcept: Bool,
        session: GameSession? = nil,
        onRewind: (@MainActor () -> Void)? = nil,
        onClose: @escaping @MainActor () -> Void
    ) {
        let context = LessonViewModel.context(life: session?.life, usesSampleData: session?.usesSampleData ?? false)
        let model = LessonViewModel(lesson: lesson, isNewConcept: isNewConcept, context: context)
        model.onRewind = onRewind
        _model = State(initialValue: model)
        self.onClose = onClose
        self.onRewind = onRewind
    }

    var body: some View {
        LessonView(state: model.state.presented(presentation), actions: model.actions)
            .onAppear {
                model.onClose = onClose
                model.onRewind = onRewind
            }
    }
}
