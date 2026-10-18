import SwiftUI

/// Glue: owns `ConceptCollectionViewModel` and feeds `ConceptCollectionView`.
struct ConceptCollectionScreen: View {
    @State private var model: ConceptCollectionViewModel
    /// The Learn course (ADR 0068): the path order is the main way to learn these concepts.
    @State private var learn: LearnPathViewModel
    @State private var showsLearn = false
    private let client: any LifelineClient
    private let onClose: @MainActor () -> Void

    init(client: any LifelineClient, unlockedIDs: [String], onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: ConceptCollectionViewModel(client: client, unlockedIDs: unlockedIDs))
        _learn = State(initialValue: LearnPathViewModel(client: client))
        self.client = client
        self.onClose = onClose
    }

    private var actions: ConceptCollectionActions {
        var actions = model.actions
        actions.onOpenLearn = { showsLearn = true }
        return actions
    }

    var body: some View {
        @Bindable var model = model
        ConceptCollectionView(state: model.state, actions: actions)
            .llCover(isPresented: $showsLearn) {
                LearnPathScreen(model: learn, client: client) { showsLearn = false }
            }
            .onAppear { model.onClose = onClose }
            .task { await model.load() }
            .fullScreenCover(isPresented: Binding(get: { model.selectedLesson != nil }, set: { if !$0 { model.selectedLesson = nil } })) {
                if let lesson = model.selectedLesson {
                    LessonScreen(lesson: lesson, isNewConcept: false) { model.selectedLesson = nil }
                }
            }
    }
}
