import Foundation

extension LifeSummaryViewState {
    /// Presentation mode: the person's name becomes "You", pound amounts are rounded.
    func presented(_ on: Bool) -> LifeSummaryViewState {
        guard on else { return self }
        var copy = self
        func clean(_ text: String) -> String {
            var result = text
            if !name.isEmpty {
                result = result.replacingOccurrences(of: "\(name)'s", with: "Your")
                    .replacingOccurrences(of: name, with: "You")
            }
            return PresentationFormat.text(result, true)
        }
        copy.name = "You"
        copy.title = clean(title)
        copy.shareText = clean(shareText)
        copy.indexSentence = clean(indexSentence)
        copy.causeOfDeath = causeOfDeath.map(clean)
        copy.keyMoments = keyMoments.map { var m = $0; m.text = clean(m.text); return m }
        copy.ribbons = ribbons.map { var r = $0; r.reason = clean(r.reason); return r }
        copy.netWorth = LLAmountFormat.rounded(netWorth)
        copy.autopilotNetWorth = LLAmountFormat.rounded(autopilotNetWorth)
        return copy
    }
}
