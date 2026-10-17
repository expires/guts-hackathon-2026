import SwiftUI

/// Glue for a running Same Life room (fixture data, Tier 2): live room, then results.
/// The Play tab presents it full screen after "Start".
struct RoomFlowScreen: View {
    enum Stage { case live, results }

    @State private var live: RoomLiveViewModel
    @State private var results: RoomResultViewModel
    @State private var stage: Stage = .live
    @State private var showsLesson = false
    private let onClose: @MainActor () -> Void

    init(demo: RoomDemo, onClose: @escaping @MainActor () -> Void) {
        _live = State(initialValue: RoomLiveViewModel(demo: demo))
        _results = State(initialValue: RoomResultViewModel(state: RoomResultViewModel.makeState(demo: demo)))
        self.onClose = onClose
    }

    var body: some View {
        Group {
            switch stage {
            case .live:
                RoomLiveView(state: live.state, actions: live.actions)
            case .results:
                RoomResultView(state: results.state, actions: results.actions)
            }
        }
        .onAppear {
            live.onLeave = onClose
            live.onFinish = { stage = .results }
            live.onOpenLesson = { showsLesson = true }
            results.onClose = onClose
            results.onPlayAgain = onClose
        }
        .fullScreenCover(isPresented: $showsLesson) {
            LessonScreen(lesson: LessonFixtures.rateShockLesson, isNewConcept: false) { showsLesson = false }
        }
    }
}
