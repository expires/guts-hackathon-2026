import Foundation
import UIKit

/// Pure mapping from the Learn contract to view states (ADR 0068). Tests call these directly.
enum LearnMapping {
    /// Generic symbol when the server's `icon` is not an SF Symbol on this device.
    static let fallbackSymbol = "book.closed"

    /// Sideways positions along a unit: a gentle S curve, repeated every 8 lessons.
    static let wave: [Double] = [0, 0.55, 0.85, 0.55, 0, -0.55, -0.85, -0.55]

    /// The server's SF Symbol name when this device has it, else `fallbackSymbol`.
    static func symbol(_ name: String) -> String {
        UIImage(systemName: name) == nil ? fallbackSymbol : name
    }

    /// Icons from the server that this device cannot draw. Logged by tests and the debug build.
    static func missingSymbols(in path: LearnWire.Path) -> [String] {
        let names = path.units.flatMap(\.lessons).map(\.icon)
        return Array(Set(names.filter { UIImage(systemName: $0) == nil })).sorted()
    }

    static func status(_ status: LearnWire.Summary.StatusPayload) -> LearnNodeStatus {
        switch status {
        case .passed: .passed
        case .open: .open
        case .locked: .locked
        }
    }

    /// All lessons in path order.
    static func lessons(_ path: LearnWire.Path) -> [LearnWire.Summary] {
        path.units.sorted { $0.index < $1.index }.flatMap { $0.lessons.sorted { $0.index < $1.index } }
    }

    static func lesson(_ id: String?, in path: LearnWire.Path?) -> LearnWire.Summary? {
        guard let id, let path else { return nil }
        return lessons(path).first { $0.id == id }
    }

    static func progressText(done: Int, total: Int) -> String {
        L10n.tr("\(done) of \(total) lessons")
    }

    static func lockedFallback(previous: String?) -> String {
        if let previous { return L10n.tr("Finish \(previous) first") }
        return L10n.tr("Finish the lesson before this one first")
    }

    // MARK: Play card

    static func entry(_ path: LearnWire.Path?) -> LearnEntryState {
        guard let path else { return .loading }
        let next = lesson(path.nextLessonId, in: path)
        return LearnEntryState(
            progressText: progressText(done: path.done, total: path.total),
            progress: Double(path.done) / Double(max(path.total, 1)),
            done: path.done,
            total: path.total,
            nextText: next.map { L10n.tr("Next: \($0.title)") } ?? (path.done >= path.total ? L10n.tr("Course complete") : nil),
            isLoading: false
        )
    }

    // MARK: Path

    static func pathState(
        _ path: LearnWire.Path?, phase: LoadPhase, lockedMessage: String?, isSampleData: Bool
    ) -> LearnPathViewState {
        guard let path else {
            return LearnPathViewState(
                phase: phase, units: [], progressText: "", progress: 0, nextLessonID: nil,
                lockedMessage: lockedMessage, isSampleData: isSampleData
            )
        }
        let units = path.units.sorted { $0.index < $1.index }.enumerated().map { number, unit in
            let lessons = unit.lessons.sorted { $0.index < $1.index }
            let nodes = lessons.enumerated().map { position, lesson in
                node(lesson, position: position, count: lessons.count, nextID: path.nextLessonId)
            }
            return LearnPathViewState.UnitSection(
                id: unit.id,
                eyebrow: L10n.tr("Unit \(number + 1)"),
                title: unit.title,
                description: unit.description,
                progressText: "\(unit.done)/\(unit.total)",
                progressLabel: L10n.tr("\(unit.done) of \(unit.total) lessons done"),
                progress: Double(unit.done) / Double(max(unit.total, 1)),
                nodes: nodes
            )
        }
        return LearnPathViewState(
            phase: phase,
            units: units,
            progressText: progressText(done: path.done, total: path.total),
            progress: Double(path.done) / Double(max(path.total, 1)),
            nextLessonID: path.nextLessonId,
            lockedMessage: lockedMessage,
            isSampleData: isSampleData
        )
    }

    static func node(_ lesson: LearnWire.Summary, position: Int, count: Int, nextID: String?) -> LearnPathViewState.Node {
        let status = status(lesson.status)
        let reason = status == .locked ? (lesson.lockedReason ?? lockedFallback(previous: nil)) : nil
        let bonus = lesson.lifeBonus ?? false
        var parts = [lesson.title, L10n.tr("Lesson \(position + 1) of \(count)")]
        switch status {
        case .passed: parts.append(L10n.tr("Passed"))
        case .open: parts.append(L10n.tr("Ready to start"))
        case .locked: parts.append(L10n.tr("Locked")); if let reason { parts.append(reason) }
        }
        if bonus { parts.append(L10n.tr("Also earned in a Life game")) }
        return LearnPathViewState.Node(
            id: lesson.id,
            title: lesson.title,
            symbol: symbol(lesson.icon),
            status: status,
            lockedReason: reason,
            hasLifeBonus: bonus,
            isNext: lesson.id == nextID,
            offset: wave[position % wave.count],
            accessibilityLabel: parts.joined(separator: ". ")
        )
    }

    // MARK: Lesson

    /// The first money amount or percentage in a fact, for the big number: "£25,000", "9%", "£1,270.50".
    static func number(in text: String) -> String? {
        let pattern = /£\d[\d,]*(?:\.\d+)?(?:\s?(?:million|billion|bn|m)\b)?|\d[\d,]*(?:\.\d+)?%/
        return text.firstMatch(of: pattern).map { String($0.output) }
    }

    /// "Checked 17 Oct 2026" from an ISO date. The raw text when it is not a date.
    static func checkedText(_ iso: String, language: AppLanguage = .current) -> String {
        let parser = DateFormatter()
        parser.locale = Locale(identifier: "en_US_POSIX")
        parser.timeZone = TimeZone(identifier: "UTC")
        parser.dateFormat = "yyyy-MM-dd"
        guard let date = parser.date(from: String(iso.prefix(10))) else { return L10n.tr("Checked \(iso)") }
        let formatted = date.formatted(Date.FormatStyle(date: .abbreviated, time: .omitted, locale: language.locale, timeZone: TimeZone(identifier: "UTC")!))
        return L10n.tr("Checked \(formatted)")
    }

    static func lessonState(
        lessonID: String,
        fallbackTitle: String,
        lesson: LearnWire.Lesson?,
        unitTitle: String?,
        phase: LoadPhase,
        step: LearnLessonViewState.Step,
        answers: [String: String],
        attempt: LearnWire.AttemptResult?,
        isSubmitting: Bool,
        errorText: String?,
        isSampleData: Bool
    ) -> LearnLessonViewState {
        let graded = Dictionary(uniqueKeysWithValues: (attempt?.results ?? []).map { ($0.questionId, $0) })
        let cards = (lesson?.cards ?? []).enumerated().map { LearnLessonViewState.Card(id: $0, title: $1.title, text: $1.text) }
        let facts = (lesson?.facts ?? []).enumerated().map { index, fact in
            LearnLessonViewState.Fact(
                id: index, number: number(in: fact.text), text: fact.text, sourceLabel: fact.sourceLabel,
                sourceURL: URL(string: fact.sourceUrl).flatMap { ["https", "http"].contains($0.scheme?.lowercased() ?? "") ? $0 : nil },
                checkedText: checkedText(fact.checked)
            )
        }
        let questions = (lesson?.quiz ?? []).map { question in
            let grade = graded[question.id]
            return LearnLessonViewState.Question(
                id: question.id,
                text: question.text,
                choices: question.choices.map { .init(id: $0.id, text: $0.text) },
                selectedChoiceID: answers[question.id],
                isCorrect: grade?.correct,
                correctChoiceID: grade?.correctChoiceId,
                explanation: grade?.explanation
            )
        }
        return LearnLessonViewState(
            phase: phase,
            lessonID: lessonID,
            title: lesson?.summary.title ?? fallbackTitle,
            symbol: symbol(lesson?.summary.icon ?? fallbackSymbol),
            unitTitle: unitTitle,
            cards: cards,
            facts: facts,
            questions: questions,
            step: step,
            result: attempt.map { result(lessonID: lessonID, attempt: $0) },
            isSubmitting: isSubmitting,
            errorText: errorText,
            isSampleData: isSampleData
        )
    }

    /// The lesson "Next lesson" opens after a pass: the one this attempt unlocked, else the next lesson on the
    /// path when it is not locked (a lesson passed before unlocks nothing new).
    static func nextLesson(after lessonID: String, attempt: LearnWire.AttemptResult) -> LearnWire.Summary? {
        guard attempt.passed else { return nil }
        if let unlocked = lesson(attempt.unlockedLessonId, in: attempt.path) { return unlocked }
        let all = lessons(attempt.path)
        guard let index = all.firstIndex(where: { $0.id == lessonID }), index + 1 < all.count else { return nil }
        let next = all[index + 1]
        return next.status == .locked ? nil : next
    }

    static func result(lessonID: String, attempt: LearnWire.AttemptResult) -> LearnLessonViewState.Result {
        let total = attempt.results.count
        let next = nextLesson(after: lessonID, attempt: attempt)
        return LearnLessonViewState.Result(
            passed: attempt.passed,
            scoreText: L10n.tr("\(attempt.correct) of \(total) right"),
            headline: attempt.passed ? L10n.tr("Lesson passed!") : L10n.tr("Not this time"),
            detail: attempt.passed
                ? (next == nil ? L10n.tr("You finished every lesson so far. Nice work.") : L10n.tr("The next lesson is open."))
                : L10n.tr("You need \(attempt.passMark) of \(total) to pass. Read why below, then try again."),
            nextLessonID: next?.id,
            nextText: next.map { L10n.tr("Next: \($0.title)") }
        )
    }
}
