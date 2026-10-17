import Foundation
import Observation

/// Main game screen: who you are, stats, Index, net worth, AGE, and the year-by-year feed.
@MainActor
@Observable
final class LifeViewModel {
    enum Route: Equatable {
        case activities
        case rewind
        case concepts
        case sources
        case summary
        case decision
        /// The open event, full screen.
        case event
        /// A Life action menu.
        case menu(LifeMenuViewState.Menu)
    }

    private let session: GameSession
    @ObservationIgnored var onRoute: @MainActor (Route) -> Void = { _ in }

    init(session: GameSession) {
        self.session = session
    }

    var state: LifeViewState {
        guard let life = session.life else { return Self.emptyState }
        return Self.makeState(
            life: life,
            outcome: session.lastOutcome,
            isBusy: session.isBusy,
            ageCount: session.ageCount,
            usesSampleData: session.usesSampleData,
            hasRewindPass: session.hasRewindPass
        )
    }

    var actions: LifeActions {
        LifeActions(
            onAge: { [weak self] in Task { await self?.session.age() } },
            onDismissOutcome: { [weak self] in self?.session.dismissOutcome() },
            onOpenActivities: { [weak self] in self?.onRoute(.activities) },
            onOpenRewind: { [weak self] in self?.onRoute(.rewind) },
            onOpenConcepts: { [weak self] in self?.onRoute(.concepts) },
            onOpenSources: { [weak self] in self?.onRoute(.sources) },
            onOpenSummary: { [weak self] in self?.onRoute(.summary) },
            onOpenDecision: { [weak self] in self?.onRoute(.decision) },
            onNewLife: { [weak self] in self?.session.newLife() },
            onOpenEvent: { [weak self] in self?.onRoute(.event) },
            onOpenMenu: { [weak self] in self?.onRoute(.menu($0)) }
        )
    }

    static func makeState(
        life: Life,
        outcome: Outcome?,
        isBusy: Bool,
        ageCount: Int,
        usesSampleData: Bool,
        hasRewindPass: Bool
    ) -> LifeViewState {
        let canAge = life.alive && life.pendingEvents.isEmpty && !isBusy
        let hint: String
        if !life.alive {
            hint = "This life is over."
        } else if !life.pendingEvents.isEmpty {
            hint = "Answer the open event first."
        } else {
            hint = "Live one more year."
        }
        let hasPass = hasRewindPass || life.rewind.hasPass == true
        let rewindText: String
        if hasPass {
            rewindText = "Rewind Pass: unlimited rewinds"
        } else if life.rewind.freeLeft == 1 {
            rewindText = "1 free rewind left"
        } else {
            rewindText = "\(life.rewind.freeLeft) free rewinds left"
        }
        let pending = life.pendingEvents.first.map { event in
            LifeViewState.PendingEvent(
                id: event.id,
                title: event.title,
                subtitle: "Choose before you age up",
                area: area(event.area.rawValue),
                areaLabel: area(event.area.rawValue).capitalized
            )
        }
        return LifeViewState(
            header: .init(
                emoji: life.character.emoji ?? "🙂",
                name: life.character.name,
                age: life.age,
                year: life.year,
                jobTitle: life.job?.title ?? "No job",
                town: life.character.town,
                isAlive: life.alive,
                causeOfDeath: life.causeOfDeath
            ),
            headerLine: ["Age \(life.age)", life.job?.title ?? life.character.occupation.capitalized, life.character.town].joined(separator: " · "),
            cash: life.finances.cash,
            years: yearGroups(life.history),
            pendingEvent: pending,
            menu: LifeMenuViewModel.makeState(life: life),
            netWorth: life.finances.netWorth,
            index: life.index.value,
            stats: StateMapping.stats(life.stats),
            outcome: outcome.map(StateMapping.outcome),
            canAge: canAge,
            isAging: isBusy,
            ageHint: hint,
            ageCount: ageCount,
            history: StateMapping.history(life.history),
            usesSampleData: usesSampleData,
            conceptsUnlocked: life.conceptsUnlocked.count,
            rewindText: rewindText,
            canRewind: life.history.contains { $0.decisionId != nil },
            activitiesCount: life.availableActions.filter { $0.tab == .activities }.count,
            showsSummary: !life.alive,
            showsDecision: life.mode == ._self && life.reachedPresent == true
        )
    }

    /// Event area to one of the 5 colour areas.
    static func area(_ raw: String) -> String {
        switch raw {
        case "work", "employer", "study": "work"
        case "home", "bills", "place": "home"
        case "money", "state": "money"
        case "family": "family"
        case "health": "health"
        default: "other"
        }
    }

    /// History grouped by year, newest year first; lines keep their order within the year.
    static func yearGroups(_ log: [YearLog]) -> [LifeViewState.YearGroup] {
        var groups: [LifeViewState.YearGroup] = []
        for entry in log {
            if let index = groups.firstIndex(where: { $0.year == entry.year }) {
                groups[index].lines.append(entry.text)
            } else {
                groups.append(.init(year: entry.year, age: entry.age, title: "\(entry.year) · Age \(entry.age)", lines: [entry.text]))
            }
        }
        return groups.reversed()
    }

    static let emptyState = LifeViewState(
        header: .init(emoji: "🙂", name: "", age: 0, year: 0, jobTitle: "", town: "", isAlive: false, causeOfDeath: nil),
        netWorth: 0,
        index: 100,
        stats: [],
        outcome: nil,
        canAge: false,
        isAging: false,
        ageHint: "",
        ageCount: 0,
        history: [],
        usesSampleData: false,
        conceptsUnlocked: 0,
        rewindText: "",
        canRewind: false,
        activitiesCount: 0,
        showsSummary: false,
        showsDecision: false
    )
}
