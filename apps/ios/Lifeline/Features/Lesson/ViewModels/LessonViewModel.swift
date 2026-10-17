import Foundation
import Observation

/// Where the lesson opened: the running life, if any. Plain values, built by the glue from `GameSession`.
struct LessonContext: Equatable, Sendable {
    var year: Int
    var age: Int
    /// Concepts unlocked in this life, including this one.
    var conceptsLearned: Int
    /// True when the life has at least one decision to rewind to.
    var hasDecision: Bool
    var isSampleData: Bool
}

/// Full-screen lesson: chart, 2 sentences, 1-tap quiz. Never paywalled.
@MainActor
@Observable
final class LessonViewModel {
    private let lesson: Lesson
    private let isNewConcept: Bool
    private let context: LessonContext?
    private(set) var selectedIndex: Int?
    @ObservationIgnored var onClose: @MainActor () -> Void = {}
    /// Nil hides "Rewind and try again".
    @ObservationIgnored var onRewind: (@MainActor () -> Void)?

    init(lesson: Lesson, isNewConcept: Bool, context: LessonContext? = nil) {
        self.lesson = lesson
        self.isNewConcept = isNewConcept
        self.context = context
    }

    var state: LessonViewState {
        Self.makeState(
            lesson: lesson,
            isNewConcept: isNewConcept,
            selectedIndex: selectedIndex,
            context: context,
            canRewind: onRewind != nil
        )
    }

    var actions: LessonActions {
        LessonActions(
            onAnswer: { [weak self] index in
                guard let self, selectedIndex == nil, lesson.quiz.options.indices.contains(index) else { return }
                selectedIndex = index
            },
            onClose: { [weak self] in self?.onClose() },
            onRewind: { [weak self] in self?.onRewind?() }
        )
    }

    static func makeState(
        lesson: Lesson,
        isNewConcept: Bool,
        selectedIndex: Int?,
        context: LessonContext? = nil,
        canRewind: Bool = false
    ) -> LessonViewState {
        let chart = StateMapping.chart(lesson.chart)
        let first = chart.points.first
        let last = chart.points.last
        let hasRange = chart.points.count >= 2
        var concept = [isNewConcept ? "New concept" : "Concept", lesson.title]
        if let context { concept.append("\(context.conceptsLearned) learned") }
        return LessonViewState(
            conceptID: lesson.conceptId,
            title: lesson.title,
            chart: chart,
            sentences: lesson.sentences,
            quiz: .init(
                question: lesson.quiz.question,
                options: lesson.quiz.options,
                answerIndex: lesson.quiz.answerIndex,
                selectedIndex: selectedIndex
            ),
            isNewConcept: isNewConcept,
            personal: lesson.personal,
            eyebrow: context.map { "\($0.year) · Age \($0.age)" },
            heroLine: hasRange ? "\(format(first!.y, unit: chart.yLabel)) → \(format(last!.y, unit: chart.yLabel))" : nil,
            heroCaption: chart.title,
            changeSentence: hasRange ? changeSentence(chart: chart) : nil,
            conceptLine: concept.joined(separator: " · "),
            canRewind: canRewind && (context?.hasDecision ?? false),
            isSampleData: context?.isSampleData ?? false
        )
    }

    /// Value with its unit: "%" gives "4.1%", a "£" label gives "£1,150", anything else a plain number.
    static func format(_ value: Double, unit: String) -> String {
        if unit.contains("£") { return Money.format(value) }
        let number = value.formatted(.number.locale(Money.locale).precision(.fractionLength(0...1)))
        return unit.trimmingCharacters(in: .whitespaces) == "%" ? number + "%" : number
    }

    /// "Up 0.9 points from 2006 to 2008." for a % chart, "Up £455 from 2021 to 2023." for money.
    static func changeSentence(chart: ChartState) -> String? {
        guard let first = chart.points.first, let last = chart.points.last else { return nil }
        let delta = last.y - first.y
        let from = first.label ?? String(Int(first.x))
        let to = last.label ?? String(Int(last.x))
        let size: String
        if chart.yLabel.contains("£") {
            size = Money.format(abs(delta))
        } else {
            let number = abs(delta).formatted(.number.locale(Money.locale).precision(.fractionLength(0...1)))
            size = chart.yLabel.trimmingCharacters(in: .whitespaces) == "%" ? "\(number) points" : number
        }
        if abs(delta) < 0.05 { return "No change from \(from) to \(to)." }
        return "\(delta > 0 ? "Up" : "Down") \(size) from \(from) to \(to)."
    }

    /// Context from the running life. Nil outside a life.
    static func context(life: Life?, usesSampleData: Bool) -> LessonContext? {
        guard let life else { return nil }
        return LessonContext(
            year: life.year,
            age: life.age,
            conceptsLearned: life.conceptsUnlocked.count,
            hasDecision: life.history.contains { $0.decisionId != nil },
            isSampleData: usesSampleData
        )
    }
}
