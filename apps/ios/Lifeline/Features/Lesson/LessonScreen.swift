import SwiftUI

/// Glue: owns `LessonViewModel` and feeds `LessonView`.
struct LessonScreen: View {
    @State private var model: LessonViewModel
    private let onClose: @MainActor () -> Void

    init(lesson: Lesson, isNewConcept: Bool, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: LessonViewModel(lesson: lesson, isNewConcept: isNewConcept))
        self.onClose = onClose
    }

    var body: some View {
        LessonView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
    }
}
