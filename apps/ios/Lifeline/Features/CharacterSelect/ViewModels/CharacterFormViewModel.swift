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
            name: initial?.name ?? "",
            emoji: initial?.emoji ?? "🙂",
            birthYear: initial?.birthYear ?? 1995,
            occupation: initial?.occupation ?? "",
            regionID: initial?.region ?? UKRegion.london.rawValue,
            town: initial?.town ?? "",
            income: initial?.annualIncome ?? (mode == .playYourself ? 0 : 30_000),
            savings: initial?.savings ?? 0,
            debt: initial?.debt ?? 0,
            housing: HousingOption(rawValue: initial?.housing?.rawValue ?? "rent") ?? .rent
        )
    }

    var state: CharacterFormViewState {
        CharacterFormViewState(
            mode: mode,
            title: mode == .playYourself ? L10n.tr("About you") : "God Mode",
            fields: fields,
            regions: UKRegion.allCases.map { PickerOption(id: $0.rawValue, label: $0.displayName) },
            birthYearRange: Self.birthYearRange,
            quickPicks: mode == .godMode
                ? Self.godModeJobs.map { .init(id: $0.id, emoji: $0.emoji, label: $0.id.capitalized) }
                : [],
            canContinue: Self.isValid(fields),
            // Bank connections are cut (ADR 0046): no "Fill in from my bank".
            showsBankConnect: false,
            bankStatusText: bankStatusText,
            footer: L10n.tr("Your answers stay on our server for this game only. No bank details are needed.")
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

    /// True after the user changed a field. A late profile prefill then leaves the fields alone.
    private var isEdited = false

    /// "Play yourself" starts from your money profile (`GET /v1/finance/profile`): name, birth year, job,
    /// region, town, pay, savings, debt and home. Only before the user edits anything.
    /// From the whole money profile: the character, with the birth year from the entered age
    /// (the profile's `age` is what the user typed or what the statement implies).
    func prefill(profile: FinanceProfile, now: Date = Date()) {
        var spec = profile.character
        spec.birthYear = Calendar(identifier: .gregorian).component(.year, from: now) - profile.profile.age
        if spec.annualIncome <= 0, profile.profile.annualIncome > 0 {
            spec.annualIncome = profile.profile.annualIncome
        }
        prefill(spec)
    }

    func prefill(_ spec: CharacterSpec) {
        guard mode == .playYourself, !isEdited else { return }
        fields = CharacterFormFields(
            name: spec.name,
            emoji: spec.emoji ?? fields.emoji,
            birthYear: min(Self.birthYearRange.upperBound, max(Self.birthYearRange.lowerBound, spec.birthYear)),
            occupation: spec.occupation,
            regionID: spec.region,
            town: spec.town,
            income: spec.annualIncome,
            savings: spec.savings ?? fields.savings,
            debt: spec.debt ?? fields.debt,
            housing: spec.housing.flatMap { HousingOption(rawValue: $0.rawValue) } ?? fields.housing
        )
    }

    func update(_ new: CharacterFormFields) {
        isEdited = true
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
        bankStatusText = status == .mock ? L10n.tr("Filled from your bank") : L10n.tr("Filled from your bank")
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
