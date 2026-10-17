import Foundation

/// Builds the real-life decision input from a "Play yourself" life.
enum DecisionProfileBuilder {
    static func profile(from life: Life?, currentYear: Int = 2026) -> DecisionProfile {
        guard let life else { return ContractExamples.decisionProfile }
        let character = life.character
        return DecisionProfile(
            age: min(100, max(16, currentYear - character.birthYear)),
            region: character.region,
            postcode: character.postcode,
            annualIncome: life.finances.annualIncome,
            savings: max(0, life.finances.savings),
            otherDebt: max(0, life.finances.otherDebt),
            housing: DecisionProfile.HousingPayload(rawValue: character.housing?.rawValue ?? "rent") ?? .rent,
            propertyValue: life.finances.propertyValue > 0 ? life.finances.propertyValue : nil,
            mortgageBalance: life.finances.mortgageBalance > 0 ? life.finances.mortgageBalance : nil
        )
    }
}
