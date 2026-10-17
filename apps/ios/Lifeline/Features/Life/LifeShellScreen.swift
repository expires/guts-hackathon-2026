import SwiftUI

/// Sheets that the running life can open.
enum LifeSheet: String, Identifiable {
    case activities, rewind, concepts, sources, summary, decision, store
    // Life action menus (ADR 0016).
    case job, assets, people, money
    var id: String { rawValue }

    /// W7 screens with their own header show full screen. Menus and lists show as sheets.
    var isFullScreen: Bool {
        switch self {
        case .rewind, .summary, .decision, .store: true
        case .activities, .concepts, .sources, .job, .assets, .people, .money: false
        }
    }
}

/// Glue for a running life in the Life tab (ADR 0016). `LifeView` plus the action menu bar,
/// attached with `.safeAreaInset`, so `LifeView` needs no edit. Owns the event sheet and the lesson.
struct LifeShellScreen: View {
    let session: GameSession
    @State private var sheet: LifeSheet?
    /// The open event shows full screen (handoff Life-Event) after the player taps it on the feed.
    @State private var showsEvent = false
    /// Decision to open Rewind on (from the lesson's "Rewind and try again"). Nil shows the picker.
    @State private var rewindDecisionID: String?

    var body: some View {
        NavigationStack {
            LifeScreen(session: session) { route in
                if route == .event {
                    showsEvent = true
                } else {
                    sheet = Self.sheet(for: route)
                }
            }
        }
        .fullScreenCover(isPresented: Binding(
            get: { showsEvent && session.activeEvent != nil },
            set: { if !$0 { showsEvent = false } }
        )) {
            EventSheetScreen(session: session) { showsEvent = false }
        }
        .llCover(item: $sheet.only(\.isFullScreen)) { sheet in
            content(for: sheet)
        }
        .llSheet(item: $sheet.only { !$0.isFullScreen }) { sheet in
            content(for: sheet)
        }
        .fullScreenCover(isPresented: Binding(
            get: { session.pendingLesson != nil && !showsEvent && sheet == nil },
            set: { if !$0 { session.pendingLesson = nil } }
        )) {
            if let lesson = session.pendingLesson {
                LessonScreen(
                    lesson: lesson,
                    isNewConcept: true,
                    session: session,
                    onRewind: {
                        rewindDecisionID = session.life?.history.last { $0.decisionId != nil }?.decisionId
                        session.pendingLesson = nil
                        Task { @MainActor in
                            // Wait for the lesson to close, then open Rewind.
                            try? await Task.sleep(for: .milliseconds(450))
                            sheet = .rewind
                        }
                    }
                ) { session.pendingLesson = nil }
            }
        }
    }

    private static func sheet(for route: LifeViewModel.Route) -> LifeSheet {
        switch route {
        case .activities: .activities
        case .rewind: .rewind
        case .concepts: .concepts
        case .sources: .sources
        case .summary: .summary
        case .decision: .decision
        case .event: .activities
        case let .menu(menu): sheet(for: menu)
        }
    }

    private static func sheet(for menu: LifeMenuViewState.Menu) -> LifeSheet {
        switch menu {
        case .job: .job
        case .assets: .assets
        case .people: .people
        case .money: .money
        case .activities: .activities
        }
    }

    @ViewBuilder
    private func content(for sheet: LifeSheet) -> some View {
        let close: @MainActor () -> Void = { self.sheet = nil }
        switch sheet {
        case .activities:
            ActivitiesSheetScreen(session: session, onClose: close)
        case .rewind:
            RewindScreen(session: session, decisionID: rewindDecisionID, onClose: {
                rewindDecisionID = nil
                close()
            }) { self.sheet = .store }
        case .concepts:
            ConceptCollectionScreen(client: session.client, unlockedIDs: session.life?.conceptsUnlocked ?? [], onClose: close)
        case .sources:
            SourcesScreen(client: session.client, onClose: close)
        case .summary:
            if let life = session.life {
                LifeSummaryScreen(client: session.client, lifeID: life.id, emoji: life.character.emoji ?? "🙂") {
                    self.sheet = nil
                    session.newLife()
                } onClose: { close() }
            }
        case .decision:
            RealLifeDecisionScreen(
                client: session.client,
                profile: DecisionProfileBuilder.profile(from: session.life),
                lifeID: session.life?.id,
                onClose: close
            )
        case .store:
            StoreScreen(session: session, onClose: close)
        case .job:
            JobTabScreen(session: session, onClose: close)
        case .assets:
            AssetsTabScreen(session: session, onClose: close)
        case .people:
            PeopleTabScreen(session: session, onClose: close)
        case .money:
            MoneyTabScreen(session: session, onClose: close)
        }
    }
}
