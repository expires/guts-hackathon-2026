import Foundation
import Observation

/// Lists every screen and fixture state for the Playground (`-playground`).
@MainActor
@Observable
final class GalleryViewModel {
    let state: GalleryViewState = GalleryViewModel.catalog

    static let catalog = GalleryViewState(
        title: "Playground",
        sections: [
            .init(id: "app", title: "Run the app", entries: [
                .init(id: "app.flow", title: "Full app on sample data", detail: "MockClient, no backend"),
            ]),
            .init(id: "select", title: "Choose a life", entries: [
                .init(id: "select.ready", title: "Character select", detail: "Presets, Random, locked God Mode"),
                .init(id: "select.godOwned", title: "Character select", detail: "God Mode owned"),
                .init(id: "select.loading", title: "Character select", detail: "Loading"),
                .init(id: "select.offline", title: "Character select", detail: "Offline error"),
                .init(id: "form.self", title: "Play yourself form", detail: "Empty"),
                .init(id: "form.bank", title: "Play yourself form", detail: "Filled from bank (sample)"),
                .init(id: "form.god", title: "God Mode form", detail: "Banker quick pick"),
                .init(id: "year.preset", title: "Start year", detail: "Preset"),
                .init(id: "year.starting", title: "Start year", detail: "Starting"),
            ]),
            .init(id: "life", title: "Life", entries: [
                .init(id: "life.new", title: "Life", detail: "New life"),
                .init(id: "life.mid", title: "Life", detail: "Mid-life with good outcome"),
                .init(id: "life.event", title: "Life", detail: "Event open, AGE blocked"),
                .init(id: "life.bad", title: "Life", detail: "Bad outcome, Rewind Pass"),
                .init(id: "life.dead", title: "Life", detail: "Dead"),
                .init(id: "event.rent", title: "Event sheet", detail: "Rent rise, cached source, UK average"),
                .init(id: "event.crisis", title: "Event sheet", detail: "Crisis, AI text, mock source"),
                .init(id: "event.submitting", title: "Event sheet", detail: "Submitting"),
                .init(id: "activities.list", title: "Activities", detail: "With a paid action"),
                .init(id: "activities.empty", title: "Activities", detail: "Empty"),
            ]),
            .init(id: "tabs", title: "Tabs", entries: [
                .init(id: "job.normal", title: "Job", detail: "Mid-life"),
                .init(id: "job.risk", title: "Job", detail: "Employer in trouble"),
                .init(id: "job.none", title: "Job", detail: "No job"),
                .init(id: "assets.mid", title: "Assets", detail: "Home, pension, ISA"),
                .init(id: "assets.empty", title: "Assets", detail: "Empty"),
                .init(id: "people.mid", title: "People", detail: "Family"),
                .init(id: "money.mid", title: "Money", detail: "Mortgage"),
                .init(id: "money.new", title: "Money", detail: "New life with outcome"),
            ]),
            .init(id: "learn", title: "Learn", entries: [
                .init(id: "lesson.new", title: "Lesson", detail: "Unanswered"),
                .init(id: "lesson.correct", title: "Lesson", detail: "Right answer"),
                .init(id: "lesson.wrong", title: "Lesson", detail: "Wrong answer"),
                .init(id: "concepts.ready", title: "Concepts", detail: "2 unlocked"),
                .init(id: "concepts.loading", title: "Concepts", detail: "Loading"),
                .init(id: "concepts.error", title: "Concepts", detail: "Error"),
            ]),
            .init(id: "rewind", title: "Rewind and summary", entries: [
                .init(id: "rewind.picker", title: "Rewind picker", detail: "1 free rewind"),
                .init(id: "rewind.pass", title: "Rewind picker", detail: "Needs Rewind Pass"),
                .init(id: "rewind.result", title: "Rewind result", detail: "Abandoned against new"),
                .init(id: "summary.death", title: "Life summary", detail: "Death"),
                .init(id: "summary.loading", title: "Life summary", detail: "Loading"),
                .init(id: "summary.error", title: "Life summary", detail: "Error"),
            ]),
            .init(id: "rooms", title: "Same Life (PvP)", entries: [
                .init(id: "room.entry", title: "Room", detail: "Create or join"),
                .init(id: "room.lobby", title: "Room lobby", detail: "4 players"),
                .init(id: "room.joining", title: "Room", detail: "Joining"),
                .init(id: "room.rivals", title: "Rival strip", detail: "4 players live"),
                .init(id: "room.result", title: "Room result", detail: "End comparison"),
            ]),
            .init(id: "other", title: "Decision, store, bank, data", entries: [
                .init(id: "decision.ready", title: "Real-life decision", detail: "Fix for 5 years"),
                .init(id: "decision.loading", title: "Real-life decision", detail: "Loading"),
                .init(id: "decision.error", title: "Real-life decision", detail: "Error"),
                .init(id: "store.fresh", title: "Store", detail: "Demo payment"),
                .init(id: "store.purchasing", title: "Store", detail: "Purchasing"),
                .init(id: "store.owned", title: "Store", detail: "Rewind Pass owned"),
                .init(id: "bank.intro", title: "Bank connect", detail: "Intro"),
                .init(id: "bank.connecting", title: "Bank connect", detail: "Connecting"),
                .init(id: "bank.connected", title: "Bank connect", detail: "Connected, sample data"),
                .init(id: "bank.failed", title: "Bank connect", detail: "Failed"),
                .init(id: "sources.ready", title: "Data sources", detail: "Live, saved copy, sample"),
                .init(id: "sources.loading", title: "Data sources", detail: "Loading"),
                .init(id: "sources.error", title: "Data sources", detail: "Error"),
                .init(id: "debug.live", title: "Debug menu", detail: "Live client"),
                .init(id: "debug.presenter", title: "Debug menu", detail: "Presenter device id"),
                .init(id: "common.error", title: "Error state", detail: "Offline"),
                .init(id: "common.startAge", title: "Error state", detail: "Start age too low (422)"),
                .init(id: "common.loading", title: "Loading state", detail: "Generic"),
            ]),
        ]
    )
}
