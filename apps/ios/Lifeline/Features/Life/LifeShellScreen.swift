import SwiftUI

/// Tabs shown while a life is running (ADR 0009): Life, Job, Assets, People, Money.
enum LifeTab: String, Hashable, CaseIterable {
    case life, job, assets, people, money

    var title: String {
        switch self {
        case .life: "Life"
        case .job: "Job"
        case .assets: "Assets"
        case .people: "People"
        case .money: "Money"
        }
    }

    var systemImage: String {
        switch self {
        case .life: "heart.text.square"
        case .job: "briefcase"
        case .assets: "house"
        case .people: "person.2"
        case .money: "sterlingsign.circle"
        }
    }
}

/// Sheets that the running life can open.
enum LifeSheet: String, Identifiable {
    case activities, rewind, concepts, sources, summary, decision, store
    var id: String { rawValue }
}

/// Glue for a running life. Owns the tab bar and the event sheet, so an open event shows on any tab.
struct LifeShellScreen: View {
    let session: GameSession
    @State private var selection: LifeTab = .life
    @State private var sheet: LifeSheet?

    var body: some View {
        @Bindable var session = session
        TabView(selection: $selection) {
            Tab(LifeTab.life.title, systemImage: LifeTab.life.systemImage, value: LifeTab.life) {
                NavigationStack {
                    LifeScreen(session: session) { route in sheet = Self.sheet(for: route) }
                }
            }
            Tab(LifeTab.job.title, systemImage: LifeTab.job.systemImage, value: LifeTab.job) {
                NavigationStack { JobTabScreen(session: session) }
            }
            Tab(LifeTab.assets.title, systemImage: LifeTab.assets.systemImage, value: LifeTab.assets) {
                NavigationStack { AssetsTabScreen(session: session) }
            }
            Tab(LifeTab.people.title, systemImage: LifeTab.people.systemImage, value: LifeTab.people) {
                NavigationStack { PeopleTabScreen(session: session) }
            }
            Tab(LifeTab.money.title, systemImage: LifeTab.money.systemImage, value: LifeTab.money) {
                NavigationStack { MoneyTabScreen(session: session) }
            }
        }
        .sheet(isPresented: Binding(get: { session.activeEvent != nil && sheet == nil }, set: { _ in })) {
            EventSheetScreen(session: session)
                .interactiveDismissDisabled()
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.hidden)
        }
        .sheet(item: $sheet) { sheet in
            content(for: sheet)
        }
        .fullScreenCover(isPresented: Binding(
            get: { session.pendingLesson != nil && session.activeEvent == nil && sheet == nil },
            set: { if !$0 { session.pendingLesson = nil } }
        )) {
            if let lesson = session.pendingLesson {
                LessonScreen(lesson: lesson, isNewConcept: true) { session.pendingLesson = nil }
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
        }
    }

    @ViewBuilder
    private func content(for sheet: LifeSheet) -> some View {
        let close: @MainActor () -> Void = { self.sheet = nil }
        switch sheet {
        case .activities:
            ActivitiesSheetScreen(session: session, onClose: close)
                .presentationDetents([.medium, .large])
        case .rewind:
            RewindScreen(session: session, onClose: close) { self.sheet = .store }
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
        }
    }
}
