import Foundation

enum CharacterFormMode: String, Hashable, Sendable {
    case playYourself
    case godMode
}

enum HousingOption: String, Equatable, Sendable, CaseIterable, Identifiable {
    case parents
    case rent
    case own
    case mortgage

    var id: String { rawValue }

    var label: String {
        switch self {
        case .parents: "With parents"
        case .rent: "Renting"
        case .own: "Own outright"
        case .mortgage: "Paying a mortgage"
        }
    }
}

/// Generic picker option.
struct PickerOption: Equatable, Sendable, Hashable, Identifiable {
    var id: String
    var label: String
}

/// Editable fields. The View sends a full copy back through `onChange`.
struct CharacterFormFields: Equatable, Sendable {
    var name: String
    var emoji: String
    var birthYear: Int
    var occupation: String
    var regionID: String
    var town: String
    var income: Double
    var savings: Double
    var debt: Double
    var housing: HousingOption
}

struct CharacterFormViewState: Equatable, Sendable {
    struct QuickPick: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String
        var label: String
    }

    var mode: CharacterFormMode
    var title: String
    var fields: CharacterFormFields
    var regions: [PickerOption]
    var birthYearRange: ClosedRange<Int>
    /// God Mode only: one-tap jobs.
    var quickPicks: [QuickPick]
    var canContinue: Bool
    /// Play yourself only: offer a bank connection to prefill the form.
    var showsBankConnect: Bool
    /// For example "Filled from your bank (sample data)".
    var bankStatusText: String?
    var footer: String
}

struct CharacterFormActions {
    var onChange: @MainActor (CharacterFormFields) -> Void = { _ in }
    var onQuickPick: @MainActor (String) -> Void = { _ in }
    var onConnectBank: @MainActor () -> Void = {}
    var onContinue: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
