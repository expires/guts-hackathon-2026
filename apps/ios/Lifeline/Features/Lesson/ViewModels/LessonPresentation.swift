import Foundation

extension LessonViewState {
    /// Presentation mode: pound amounts in the hero line, change sentence and personal line are rounded.
    func presented(_ on: Bool) -> LessonViewState {
        guard on else { return self }
        var copy = self
        copy.heroLine = heroLine.map { PresentationFormat.text($0, true) }
        copy.changeSentence = changeSentence.map { PresentationFormat.text($0, true) }
        copy.personal = personal.map { PresentationFormat.text($0, true) }
        copy.sentences = sentences.map { PresentationFormat.text($0, true) }
        return copy
    }
}
