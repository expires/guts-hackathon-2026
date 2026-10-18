import SwiftUI

/// Glue for "Why?": evidence plus the lesson. Opens the full lesson and, for mortgage moves,
/// W7's Real-life Decision screen.
struct NextMoveWhyScreen: View {
    let client: any LifelineClient
    @State private var model: NextMoveWhyViewModel
    @State private var showsDecision = false
    @Environment(\.appRoutes) private var routes
    private let onTestIt: @MainActor (String) -> Void
    private let onClose: @MainActor () -> Void

    init(
        client: any LifelineClient,
        move: Move,
        isSampleData: Bool,
        scrollToSources: Bool = false,
        onTestIt: @escaping @MainActor (String) -> Void,
        onClose: @escaping @MainActor () -> Void
    ) {
        self.client = client
        _model = State(initialValue: NextMoveWhyViewModel(client: client, move: move, isSampleData: isSampleData))
        self.onTestIt = onTestIt
        self.onClose = onClose
        self.scrollToSources = scrollToSources
    }

    private let scrollToSources: Bool

    /// The model's actions plus "Ask Penny a follow-up": close Why first, then open Penny from the root.
    private var whyActions: NextMoveWhyActions {
        var actions = model.actions
        let routes = self.routes
        let moveID = model.move.id
        let headline = model.move.headline
        let close = onClose
        actions.onAskPenny = {
            close()
            Task { @MainActor in
                try? await Task.sleep(for: .milliseconds(450))
                routes.askPenny(PennyRoute(screen: .why, nextMoveID: moveID, question: PennyQuestion.why, title: String(headline.prefix(80))))
            }
        }
        return actions
    }

    var body: some View {
        NextMoveWhyView(state: model.state, actions: whyActions, scrollToSources: scrollToSources, onTestIt: model.move.testable ? { onTestIt(model.move.id) } : nil)
            .onAppear {
                model.onClose = onClose
                model.onOpenDecision = { showsDecision = true }
            }
            .task { await model.load() }
            .llCover(isPresented: Binding(
                get: { model.presentedLesson != nil },
                set: { if !$0 { model.presentedLesson = nil } }
            )) {
                if let lesson = model.presentedLesson {
                    LessonScreen(lesson: lesson, isNewConcept: false) { model.presentedLesson = nil }
                }
            }
            .llCover(isPresented: $showsDecision) {
                if let character = model.character {
                    RealLifeDecisionScreen(
                        client: client,
                        moveID: model.move.id,
                        character: character,
                        daysLeft: model.move.daysLeft,
                        onTestIt: model.move.testable ? { id in
                            showsDecision = false
                            onTestIt(id)
                        } : nil,
                        onClose: { showsDecision = false }
                    )
                }
            }
    }
}
