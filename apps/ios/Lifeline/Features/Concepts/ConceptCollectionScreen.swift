import SwiftUI

/// Glue: owns `ConceptCollectionViewModel` and feeds `ConceptCollectionView`.
struct ConceptCollectionScreen: View {
    @State private var model: ConceptCollectionViewModel
    private let onClose: @MainActor () -> Void

    init(client: any LifelineClient, unlockedIDs: [String], onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: ConceptCollectionViewModel(client: client, unlockedIDs: unlockedIDs))
        self.onClose = onClose
    }

    var body: some View {
        @Bindable var model = model
        ConceptCollectionView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
            .task { await model.load() }
            .fullScreenCover(isPresented: Binding(get: { model.selectedLesson != nil }, set: { if !$0 { model.selectedLesson = nil } })) {
                if let lesson = model.selectedLesson {
                    LessonScreen(lesson: lesson, isNewConcept: false) { model.selectedLesson = nil }
                }
            }
    }
}
