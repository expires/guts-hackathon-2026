import Foundation

/// Lesson fixtures for previews and the Playground (W7, ADR 0026). Every state goes through `LessonViewModel.makeState`.
@MainActor
enum LessonFixtures {
    /// The contract example lesson inside the mid-life fixture, with Rewind wired.
    static var inLife: LessonViewState {
        LessonViewModel.makeState(
            lesson: ContractExamples.lesson,
            isNewConcept: true,
            selectedIndex: nil,
            context: LessonViewModel.context(life: Fixtures.midLife, usesSampleData: true),
            canRewind: true
        )
    }

    /// Rate shock: 2-year fix payment, Sep 2021 to Sep 2023 (handoff "Data used", BoE IUMBV34).
    /// £180,000 over 25 years: 1.20% gives £695 a month, 5.91% gives £1,150 a month.
    static let rateShockLesson: Lesson = ContractExamples.decode(rateShockJSON)

    static var rateShock: LessonViewState {
        LessonViewModel.makeState(
            lesson: rateShockLesson,
            isNewConcept: true,
            selectedIndex: nil,
            context: LessonContext(year: 2023, age: 31, conceptsLearned: 4, hasDecision: true, isSampleData: true),
            canRewind: true
        )
    }

    static var all: [(id: String, title: String, state: LessonViewState)] {
        [
            ("lesson.inLife", "In a life, Rewind wired", inLife),
            ("lesson.rateShock", "Rate shock, money chart", rateShock),
        ]
    }

    static let rateShockJSON = #"""
    {
      "concept_id": "rate-shock",
      "title": "My fixed deal ended. My payment jumped.",
      "chart": {
        "kind": "line",
        "title": "a month",
        "x_label": "Month",
        "y_label": "£",
        "points": [
          {"x": 2021.0, "y": 695.0, "label": "Sep 2021"},
          {"x": 2022.0, "y": 695.0, "label": "Sep 2022"},
          {"x": 2023.0, "y": 1150.0, "label": "Sep 2023"}
        ],
        "source": {"source": "boe", "series_id": "IUMBV34", "status": "mock", "note": "Fixture from the handoff data"}
      },
      "sentences": [
        "A fix keeps my payment the same only until the deal ends. Then I pay the rates of that day.",
        "The 2-year fix at 1.20% ended. The new rate was 5.91%."
      ],
      "quiz": {
        "question": "Your 2-year fix ends when rates are high. What happens to your payment?",
        "options": ["It stays the same", "It goes up", "It goes down"],
        "answer_index": 1
      }
    }
    """#
}
