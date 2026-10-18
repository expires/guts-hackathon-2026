import SwiftUI

/// Glue for the Learn path (ADR 0068). The model is shared with the Play card, so progress shows in both.
struct LearnPathScreen: View {
    @Bindable var model: LearnPathViewModel
    let client: any LifelineClient
    let onClose: @MainActor () -> Void

    var body: some View {
        LearnPathView(state: model.state, actions: model.actions)
            .onAppear { model.onClose = onClose }
            .task { await model.load() }
            .llCover(item: $model.openLesson) { route in
                LearnLessonScreen(route: route, path: model, client: client) { model.openLesson = nil }
            }
    }
}

/// Glue for one lesson. "Next lesson" swaps the lesson in place; the cover stays open.
struct LearnLessonScreen: View {
    let path: LearnPathViewModel
    let client: any LifelineClient
    let onClose: @MainActor () -> Void
    @State private var route: LearnPathViewModel.LessonRoute
    @State private var penny: PennyContext?

    init(route: LearnPathViewModel.LessonRoute, path: LearnPathViewModel, client: any LifelineClient, onClose: @escaping @MainActor () -> Void) {
        self.path = path
        self.client = client
        self.onClose = onClose
        _route = State(initialValue: route)
    }

    var body: some View {
        LearnLessonContent(
            route: route,
            path: path,
            client: client,
            onNext: { id in route = .init(id: id, title: LearnMapping.lesson(id, in: path.path)?.title ?? "") },
            onAskPenny: { penny = $0 },
            onClose: onClose
        )
        .id(route.id)
        .pennySheet($penny, client: client)
    }
}

private struct LearnLessonContent: View {
    @State private var model: LearnLessonViewModel
    private let path: LearnPathViewModel
    private let onNext: @MainActor (String) -> Void
    private let onAskPenny: @MainActor (PennyContext) -> Void
    private let onClose: @MainActor () -> Void

    init(
        route: LearnPathViewModel.LessonRoute,
        path: LearnPathViewModel,
        client: any LifelineClient,
        onNext: @escaping @MainActor (String) -> Void,
        onAskPenny: @escaping @MainActor (PennyContext) -> Void,
        onClose: @escaping @MainActor () -> Void
    ) {
        _model = State(initialValue: LearnLessonViewModel(
            lessonID: route.id, title: route.title, unitTitle: path.unitTitle(for: route.id),
            service: path.service, client: client, isSampleData: path.isSampleData
        ))
        self.path = path
        self.onNext = onNext
        self.onAskPenny = onAskPenny
        self.onClose = onClose
    }

    var body: some View {
        LearnLessonView(state: model.state, actions: model.actions)
            .onAppear {
                model.onPathUpdate = { [path] in path.applyAttempt($0) }
                model.onNextLesson = onNext
                model.onAskPenny = onAskPenny
                model.onClose = onClose
                // A stale path offered a locked lesson: show the server's reason on the path.
                model.onLocked = { [path, onClose] reason in
                    path.showLocked(reason)
                    onClose()
                    Task { await path.load() }
                }
            }
            .task { await model.load() }
    }
}
