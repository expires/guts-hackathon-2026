import Foundation

/// What the player picked on the character select screen. Becomes a `CreateLifeRequest` after the start year is set.
struct CharacterChoice: Hashable {
    let mode: CreateLifeRequest.ModePayload
    let character: CharacterSpec

    static let minStartYear = 1990
    static let maxStartYear = 2026

    /// The simulation needs the character to be at least this old at the start (422 `invalid_input` otherwise).
    static let minStartAge = 16

    /// Earliest start year: the year the character turns 16, but not before 1990.
    /// When the character turns 16 after 2026, the range is only 2026 (the backend then rejects it with a clear message).
    var startYearRange: ClosedRange<Int> {
        let lower = min(Self.maxStartYear, max(Self.minStartYear, character.birthYear + Self.minStartAge))
        return lower...Self.maxStartYear
    }

    /// Default start year: the year the character turns 18, inside the allowed range.
    var defaultStartYear: Int {
        min(startYearRange.upperBound, max(startYearRange.lowerBound, character.birthYear + 18))
    }

    func request(startYear: Int) -> CreateLifeRequest {
        switch mode {
        case .preset:
            CreateLifeRequest(mode: .preset, startYear: startYear, presetId: character.id)
        case .random:
            // The contract has no field for "this random person". The example id is "random-<seed>",
            // so send that seed. The backend then draws the same person. See the W6 report.
            CreateLifeRequest(mode: .random, startYear: startYear, seed: Self.seed(fromRandomID: character.id))
        case ._self, .god:
            CreateLifeRequest(mode: mode, startYear: startYear, character: character)
        }
    }

    /// "random-424242" -> 424242. Nil when the id has no numeric suffix.
    static func seed(fromRandomID id: String?) -> Int? {
        guard let id, let suffix = id.split(separator: "-").last, let seed = Int(suffix),
              (0...2_147_483_647).contains(seed) else { return nil }
        return seed
    }
}

/// UK regions. Mirrors `services/api/lifeline_contracts/observation.py` `REGIONS`.
enum UKRegion: String, CaseIterable, Identifiable {
    case northEast = "north-east"
    case northWest = "north-west"
    case yorkshire = "yorkshire-and-the-humber"
    case eastMidlands = "east-midlands"
    case westMidlands = "west-midlands"
    case eastOfEngland = "east-of-england"
    case london
    case southEast = "south-east"
    case southWest = "south-west"
    case wales
    case scotland
    case northernIreland = "northern-ireland"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .yorkshire: "Yorkshire and the Humber"
        case .eastOfEngland: "East of England"
        default: rawValue.split(separator: "-").map { $0.capitalized }.joined(separator: " ")
        }
    }
}
