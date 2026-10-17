import Foundation

extension YouViewState {
    /// Presentation mode: name "You", bank "Your bank", pound amounts rounded, account numbers hidden.
    func presented(_ on: Bool) -> YouViewState {
        var copy = self
        copy.isPresentationMode = on
        guard on else { return copy }
        let t = { (text: String) in PresentationFormat.text(text, true) }
        if var profile {
            let realName = profile.name
            profile.name = "You"
            profile.annualIncome = LLAmountFormat.rounded(profile.annualIncome)
            profile.savings = LLAmountFormat.rounded(profile.savings)
            profile.housingText = t(profile.housingText)
            copy.profile = profile
            if !realName.isEmpty {
                copy.personaLine = t(personaLine.replacingOccurrences(of: realName, with: "You"))
            }
        }
        copy.personaLine = t(copy.personaLine)
        copy.personalFacts = personalFacts.map(t)
        copy.bankName = PresentationFormat.bank(bankName, true)
        return copy
    }
}
