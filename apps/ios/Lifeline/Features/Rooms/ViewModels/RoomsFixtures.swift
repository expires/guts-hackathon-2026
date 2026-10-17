import Foundation

/// Same Life room demo data (W7, ADR 0026). Rooms are Tier 2 on the backend, so the Play tab runs
/// this fixture: a lobby, a live run and the results. Every screen shows "Mock data".
/// Rooms use the contract `Room` and `Player` types. Extra fields the contract does not carry yet
/// (faces, notes, the story card) live in `RoomDemo`.
struct RoomDemo: Equatable, Sendable {
    struct Story: Equatable, Sendable {
        var year: Int
        var age: Int
        var lines: [String]
        var lessonTitle: String
        var happiness: Int
        var money: Int
        var bank: Double
    }

    struct Earned: Equatable, Sendable, Identifiable {
        /// `LLIcon` raw value.
        var icon: String
        var text: String
        var id: String { text }
    }

    var lobby: Room
    var live: Room
    var finished: Room
    /// The shared life.
    var characterName: String
    var shortName: String
    var occupation: String
    var town: String
    var birthYear: Int
    var years: Int
    var rewindsEach: Int
    var realRatesUntil: Int
    /// Face icon (`LLIcon` raw value) per player id.
    var faces: [String: String]
    /// One line per player id about their big choice, for example "Fixed for 5 years in 2021".
    var notes: [String: String]
    var story: Story
    var earned: [Earned]
    /// The player id of this device.
    var myID: String
}

@MainActor
enum RoomsFixtures {
    static let demo = RoomDemo(
        lobby: ContractExamples.decode(lobbyJSON),
        live: ContractExamples.decode(liveJSON),
        finished: ContractExamples.decode(finishedJSON),
        characterName: "Priya Shah",
        shortName: "Priya",
        occupation: "nurse",
        town: "Leeds",
        birthYear: 1992,
        years: 10,
        rewindsEach: 2,
        realRatesUntil: 2026,
        faces: ["p1": "face-teen", "p2": "face-woman-puff", "p3": "face-man-beard", "p4": "face-teen-hijab"],
        notes: [
            "p1": "Fixed for 2 years in 2021",
            "p2": "Fixed for 5 years in 2021",
            "p3": "Used a rewind",
            "p4": "Tracker rate in 2021",
        ],
        story: .init(
            year: 2023,
            age: 31,
            lines: [
                "My fix ended. My payment went from £695 to £1,150 a month.",
                "I cut my takeaway budget by £60 a month.",
            ],
            lessonTitle: "Rate shock",
            happiness: 64,
            money: 39,
            bank: 2_860
        ),
        earned: [
            .init(icon: "ribbon", text: "Rate shock survivor"),
            .init(icon: "lesson", text: "2 new concepts"),
        ],
        myID: "p1"
    )

    static var lobby: RoomLobbyViewState {
        RoomLobbyViewModel.makeDemoState(demo: demo, phase: .ready)
    }

    static var live: RoomLiveViewState { RoomLiveViewModel.makeState(demo: demo) }

    static var result: RoomResultViewState { RoomResultViewModel.makeState(demo: demo) }

    static let lobbyJSON = #"""
    {
      "code": "LEEDS4", "mode": "group", "seed": 777042, "preset_id": "nurse-leeds", "start_year": 2021,
      "max_players": 6,
      "players": [
        {"id": "p1", "name": "You", "is_host": true, "life_id": "lf_room01", "finished": false},
        {"id": "p2", "name": "Ava", "is_host": false, "life_id": "lf_room02", "finished": false},
        {"id": "p3", "name": "Tom", "is_host": false, "life_id": "lf_room03", "finished": false},
        {"id": "p4", "name": "Jas", "is_host": false, "finished": false}
      ],
      "join_url": "lifeline://join/LEEDS4", "qr_png_base64": "iVBORw0KGgo=", "status": "lobby"
    }
    """#

    static let liveJSON = #"""
    {
      "code": "LEEDS4", "mode": "group", "seed": 777042, "preset_id": "nurse-leeds", "start_year": 2021,
      "max_players": 6,
      "players": [
        {"id": "p1", "name": "You", "is_host": true, "life_id": "lf_room01", "age": 31, "year": 2023, "net_worth": 41200, "index": 96, "finished": false},
        {"id": "p2", "name": "Ava", "is_host": false, "life_id": "lf_room02", "age": 33, "year": 2025, "net_worth": 52800, "index": 108, "finished": false},
        {"id": "p3", "name": "Tom", "is_host": false, "life_id": "lf_room03", "age": 30, "year": 2022, "net_worth": 38900, "index": 99, "finished": false},
        {"id": "p4", "name": "Jas", "is_host": false, "life_id": "lf_room04", "age": 32, "year": 2024, "net_worth": 35100, "index": 91, "finished": false}
      ],
      "join_url": "lifeline://join/LEEDS4", "qr_png_base64": "iVBORw0KGgo=", "status": "playing"
    }
    """#

    static let finishedJSON = #"""
    {
      "code": "LEEDS4", "mode": "group", "seed": 777042, "preset_id": "nurse-leeds", "start_year": 2021,
      "max_players": 6,
      "players": [
        {"id": "p1", "name": "You", "is_host": true, "life_id": "lf_room01", "age": 39, "year": 2031, "net_worth": 88400, "index": 104, "finished": true},
        {"id": "p2", "name": "Ava", "is_host": false, "life_id": "lf_room02", "age": 39, "year": 2031, "net_worth": 112600, "index": 131, "finished": true},
        {"id": "p3", "name": "Tom", "is_host": false, "life_id": "lf_room03", "age": 39, "year": 2031, "net_worth": 97300, "index": 112, "finished": true},
        {"id": "p4", "name": "Jas", "is_host": false, "life_id": "lf_room04", "age": 39, "year": 2031, "net_worth": 71900, "index": 91, "finished": true}
      ],
      "join_url": "lifeline://join/LEEDS4", "qr_png_base64": "iVBORw0KGgo=", "status": "finished"
    }
    """#
}
