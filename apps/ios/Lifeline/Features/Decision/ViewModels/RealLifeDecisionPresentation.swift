import Foundation

extension RealLifeDecisionViewState {
    /// Presentation mode: pound amounts and account numbers in server text are rounded or hidden.
    func presented(_ on: Bool) -> RealLifeDecisionViewState {
        guard on else { return self }
        var copy = self
        let t = { (text: String) in PresentationFormat.text(text, true) }
        copy.question = t(question)
        copy.headline = t(headline)
        copy.reasons = reasons.map(t)
        copy.evidenceSentence = t(evidenceSentence)
        copy.alternatives = alternatives.map { var a = $0; a.label = t(a.label); return a }
        return copy
    }
}
