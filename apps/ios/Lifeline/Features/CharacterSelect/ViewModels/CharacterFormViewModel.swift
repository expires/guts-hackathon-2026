import Foundation
import Observation

/// Manual character entry for "Play yourself" and God Mode.
@MainActor
@Observable
final class CharacterFormViewModel {
    let mode: CharacterFormMode
    private(set) var fields: CharacterFormFields
    private(set) var bankStatusText: String?
    @ObservationIgnored var onContinue: @MainActor (CharacterChoice) -> Void = { _ in }
    @ObservationIgnored var onConnectBank: @MainActor () -> Void = {}

    static let godModeJobs: [(id: String, emoji: String, income: Double)] = [
        ("student", "🎓", 0),
        ("nurse", "👩‍⚕️", 28_000),
        ("plumber", "🔧", 36_000),
        ("banker", "💼", 95_000),
        ("pensioner", "👵", 12_000),
    ]

    static let birthYearRange = 1930...2008

    init(mode: CharacterFormMode, initial: CharacterSpec? = nil) {
        self.mode = mode
        self.fields = CharacterFormFields(
            name: initial?.name ?? (mode == .playYourself ? "Me" : ""),
            emoji: initial?.emoji ?? "🙂",
            birthYear: initial?.birthYear ?? 1995,
            occupation: initial?.occupation ?? "",
            regionID: initial?.region ?? UKRegion.london.rawValue,
            town: initial?.town ?? "",
            income: initial?.annualIncome ?? 30_000,
            savings: initial?.savings ?? 0,
            debt: initial?.debt ?? 0,
            housing: HousingOption(rawValue: initial?.housing?.rawValue ?? "rent") ?? .rent
        )
    }

    var state: CharacterFormViewState {
        CharacterFormViewState(
            mode: mode,
            title: mode == .playYourself ? "About you" : "God Mode",
            fields: fields,
            regions: UKRegion.allCases.map { PickerOption(id: $0.rawValue, label: $0.displayName) },
            birthYearRange: Self.birthYearRange,
            quickPicks: mode == .godMode
                ? Self.godModeJobs.map { .init(id: $0.id, emoji: $0.emoji, label: $0.id.capitalized) }
                : [],
            canContinue: Self.isValid(fields),
            showsBankConnect: mode == .playYourself,
            bankStatusText: bankStatusText,
            footer: "Your answers stay on our server for this game only. No bank details are needed."
        )
    }

    var actions: CharacterFormActions {
        CharacterFormActions(
            onChange: { [weak self] in self?.update($0) },
            onQuickPick: { [weak self] in self?.quickPick($0) },
            onConnectBank: { [weak self] in self?.onConnectBank() },
            onContinue: { [weak self] in
                guard let self, Self.isValid(fields) else { return }
                onContinue(CharacterChoice(mode: mode == .playYourself ? ._self : .god, character: makeCharacter()))
            }
        )
    }

    func update(_ new: CharacterFormFields) {
        var clamped = new
        clamped.birthYear = min(Self.birthYearRange.upperBound, max(Self.birthYearRange.lowerBound, new.birthYear))
        clamped.income = max(0, new.income)
        clamped.savings = max(0, new.savings)
        clamped.debt = max(0, new.debt)
        fields = clamped
    }

    func quickPick(_ id: String) {
        guard let job = Self.godModeJobs.first(where: { $0.id == id }) else { return }
        fields.occupation = job.id
        fields.emoji = job.emoji
        fields.income = job.income
    }

    /// Prefills from a bank summary profile (Bank feature).
    func apply(bankProfile profile: DecisionProfile, status: DataStatus) {
        fields.birthYear = min(Self.birthYearRange.upperBound, max(Self.birthYearRange.lowerBound, 2026 - profile.age))
        fields.regionID = profile.region
        fields.income = profile.annualIncome
        fields.savings = profile.savings
        fields.debt = profile.otherDebt ?? 0
        fields.housing = HousingOption(rawValue: profile.housing.rawValue) ?? .rent
        bankStatusText = status == .mock ? "Filled from your bank (sample data)" : "Filled from your bank"
    }

    static func isValid(_ fields: CharacterFormFields) -> Bool {
        !fields.name.trimmingCharacters(in: .whitespaces).isEmpty
            && !fields.occupation.trimmingCharacters(in: .whitespaces).isEmpty
            && !fields.town.trimmingCharacters(in: .whitespaces).isEmpty
    }

    func makeCharacter() -> CharacterSpec {
        CharacterSpec(
            name: String(fields.name.trimmingCharacters(in: .whitespaces).prefix(40)),
            emoji: fields.emoji,
            occupation: String(fields.occupation.trimmingCharacters(in: .whitespaces).prefix(60)),
            region: fields.regionID,
            town: String(fields.town.trimmingCharacters(in: .whitespaces).prefix(60)),
            birthYear: fields.birthYear,
            annualIncome: fields.income,
            savings: fields.savings,
            debt: fields.debt,
            housing: CharacterSpec.HousingPayload(rawValue: fields.housing.rawValue)
        )
    }
}
