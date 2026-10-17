import Foundation

extension BankConnectViewState {
    /// Presentation mode: the bank is "Your bank" and amounts are rounded (the view uses `LLAmount`).
    func presented(_ on: Bool) -> BankConnectViewState {
        guard on else { return self }
        var copy = self
        copy.providerName = PresentationFormat.bank(providerName, true)
        copy.privacyNote = PresentationFormat.text(privacyNote, true)
        return copy
    }
}
