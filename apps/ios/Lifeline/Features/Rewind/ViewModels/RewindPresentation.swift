import Foundation

extension RewindPickerViewState {
    /// Presentation mode: pound amounts in every line are rounded. Raw values use `LLAmount` in the view.
    func presented(_ on: Bool) -> RewindPickerViewState {
        guard on else { return self }
        var copy = self
        let t = { (text: String) in PresentationFormat.text(text, true) }
        copy.options = options.map { var o = $0; o.text = t(o.text); o.netWorth = LLAmountFormat.rounded(o.netWorth); return o }
        copy.timeline = timeline.map(t)
        copy.didLines = didLines.map(t)
        copy.alternative = alternative.map { var a = $0; a.title = t(a.title); a.lines = a.lines.map(t); return a }
        return copy
    }
}

extension RewindResultViewState {
    func presented(_ on: Bool) -> RewindResultViewState {
        guard on else { return self }
        var copy = self
        copy.abandonedNetWorth = LLAmountFormat.rounded(abandonedNetWorth)
        copy.newNetWorth = LLAmountFormat.rounded(newNetWorth)
        copy.message = PresentationFormat.text(message, true)
        return copy
    }
}
