import Foundation

/// Offline Learn course for previews, the Playground, UI tests and unit tests (ADR 0068).
///
/// The content is the real course, recorded from `lifeline_sim.learn` into `learn-mock-course.json`
/// (with the answer keys, which only this mock has). Status rules match the server:
/// a lesson is open when it is the first one or the one before it is passed.
actor MockLearnService: LearnService {
    /// One recorded lesson with its answers.
    struct Entry: Codable, Sendable {
        var lesson: LearnWire.Lesson
        var answers: [LearnWire.AnswerResult]
    }

    struct CourseUnit: Codable, Sendable {
        var id: String
        var title: String
        var description: String
        var lessonIds: [String]

        enum CodingKeys: String, CodingKey {
            case id, title, description
            case lessonIds = "lesson_ids"
        }
    }

    struct Course: Codable, Sendable {
        var units: [CourseUnit]
        var lessons: [Entry]

        /// `Features/Learn/learn-mock-course.json` from the app bundle.
        static let bundled: Course = {
            guard let url = Bundle.main.url(forResource: "learn-mock-course", withExtension: "json"),
                  let data = try? Data(contentsOf: url),
                  let course = try? JSONDecoder().decode(Course.self, from: data) else { return .tiny }
            return course
        }()

        /// Fallback when the bundle has no recording: three lessons in one unit.
        static let tiny: Course = {
            func lesson(_ id: String, _ index: Int, _ title: String, _ icon: String) -> Entry {
                let question = { (n: Int) in
                    LearnWire.Question(id: "q\(n)", text: "Which of these is a need?", choices: [.init(id: "a", text: "Rent"), .init(id: "b", text: "A concert ticket")])
                }
                return Entry(
                    lesson: .init(
                        summary: .init(id: id, unitId: "money-basics", index: index, title: title, icon: icon, status: .locked),
                        cards: [.init(title: "Needs come first", text: "Needs are rent, food, bills and travel to uni."),
                                .init(title: "Wants can wait", text: "Wants are nice to have. Pay for them from what is left.")],
                        facts: [.init(text: "You repay 9% of what you earn above £25,000 a year (Plan 5).",
                                      sourceLabel: "gov.uk · Repaying your student loan",
                                      sourceUrl: "https://www.gov.uk/repaying-your-student-loan/what-you-pay", checked: "2026-10-17")],
                        quiz: (0..<3).map(question),
                        passMark: 2
                    ),
                    answers: (0..<3).map { .init(questionId: "q\($0)", correct: false, correctChoiceId: "a", explanation: "Rent is a need.") }
                )
            }
            return Course(
                units: [.init(id: "money-basics", title: "Money basics", description: "Needs, wants and where your money goes",
                              lessonIds: ["what-is-money", "needs-vs-wants", "budgeting"])],
                lessons: [lesson("what-is-money", 0, "What money is for", "sterlingsign.circle"),
                          lesson("needs-vs-wants", 1, "Needs and wants", "cart"),
                          lesson("budgeting", 2, "Make a budget", "list.bullet.clipboard")]
            )
        }()
    }

    /// The Playground and mock launches: a sample student with the first 4 lessons passed (ADR 0068).
    static let shared = MockLearnService(passedCount: 4, bonusCount: 2)

    let course: Course
    private(set) var passed: Set<String>
    private(set) var bonus: Set<String>
    /// Every `language` the service received, in call order. Tests read it.
    private(set) var languages: [AppLanguage] = []
    /// Number of each call, for tests.
    private(set) var attempts = 0
    private let delay: Duration

    init(course: Course = .bundled, passed: Set<String> = [], bonus: Set<String> = [], delay: Duration = .zero) {
        self.course = course
        self.passed = passed
        self.bonus = bonus
        self.delay = delay
    }

    /// The first `passedCount` lessons passed. The first `bonusCount` lessons with a Life concept after them
    /// carry the Life bonus star.
    init(course: Course = .bundled, passedCount: Int, bonusCount: Int = 0, delay: Duration = .zero) {
        let order = course.units.flatMap(\.lessonIds)
        let byID = Dictionary(uniqueKeysWithValues: course.lessons.map { ($0.lesson.summary.id, $0) })
        let bonusIDs = order.dropFirst(passedCount).filter { byID[$0]?.lesson.summary.conceptId != nil }.prefix(bonusCount)
        self.init(course: course, passed: Set(order.prefix(passedCount)), bonus: Set(bonusIDs), delay: delay)
    }

    var order: [String] { course.units.flatMap(\.lessonIds) }

    func learnPath(language: AppLanguage) async throws -> LearnWire.Path {
        languages.append(language)
        try await pause()
        return buildPath()
    }

    func learnLesson(id: String, language: AppLanguage) async throws -> LearnWire.Lesson {
        languages.append(language)
        try await pause()
        guard var found = entry(id) else { throw Self.notFound(id) }
        // No locks (PENNY_V3_BUILD E1): every lesson opens.
        found.lesson.summary = summary(id)
        return found.lesson
    }

    func attemptLearnLesson(id: String, answers: [String: String], language: AppLanguage) async throws -> LearnWire.AttemptResult {
        languages.append(language)
        attempts += 1
        try await pause()
        guard let found = entry(id) else { throw Self.notFound(id) }
        let results = found.answers.map { answer in
            LearnWire.AnswerResult(
                questionId: answer.questionId,
                correct: answers[answer.questionId] == answer.correctChoiceId,
                correctChoiceId: answer.correctChoiceId,
                explanation: answer.explanation
            )
        }
        let correct = results.filter(\.correct).count
        let passMark = found.lesson.passMark ?? 2
        let didPass = correct >= passMark
        var unlocked: String?
        if didPass, !passed.contains(id) {
            passed.insert(id)
            if let index = order.firstIndex(of: id), index + 1 < order.count { unlocked = order[index + 1] }
        }
        return .init(passed: didPass, correct: correct, passMark: passMark, results: results, unlockedLessonId: unlocked, path: buildPath())
    }

    /// Test helper: the right choice per question.
    func answerKey(_ id: String) -> [String: String] {
        Dictionary(uniqueKeysWithValues: (entry(id)?.answers ?? []).map { ($0.questionId, $0.correctChoiceId) })
    }

    // MARK: Rules (same as lifeline_sim.learn)

    private func entry(_ id: String) -> Entry? {
        course.lessons.first { $0.lesson.summary.id == id }
    }

    private func summary(_ id: String) -> LearnWire.Summary {
        Self.summary(id, course: course, passed: passed, bonus: bonus)
    }

    private func buildPath() -> LearnWire.Path {
        Self.path(course: course, passed: passed, bonus: bonus)
    }

    static func summary(_ id: String, course: Course, passed: Set<String>, bonus: Set<String>) -> LearnWire.Summary {
        let title = { (id: String) in course.lessons.first { $0.lesson.summary.id == id }?.lesson.summary }
        var summary = title(id) ?? .init(id: id, unitId: "", index: 0, title: id, icon: "book", status: .locked)
        summary.lockedReason = nil
        // No locks (PENNY_V3_BUILD E1): a lesson is passed or open. The path keeps the order.
        summary.status = passed.contains(id) ? .passed : .open
        summary.lifeBonus = bonus.contains(id)
        return summary
    }

    /// The path for a set of passed lessons. Previews and fixtures call it directly.
    static func path(course: Course = .bundled, passed: Set<String>, bonus: Set<String> = []) -> LearnWire.Path {
        var next: String?
        let order = course.units.flatMap(\.lessonIds)
        let units = course.units.enumerated().map { index, unit in
            let lessons = unit.lessonIds.map { summary($0, course: course, passed: passed, bonus: bonus) }
            if next == nil { next = lessons.first { $0.status == .open }?.id }
            return LearnWire.Unit(
                id: unit.id, index: index, title: unit.title, description: unit.description, lessons: lessons,
                done: lessons.filter { $0.status == .passed }.count, total: max(lessons.count, 1)
            )
        }
        return .init(units: units, nextLessonId: next, done: passed.intersection(order).count, total: max(order.count, 1))
    }

    private func pause() async throws {
        if delay > .zero { try await Task.sleep(for: delay) }
    }

    static func locked(_ summary: LearnWire.Summary) -> APIError {
        .server(status: 409, code: LearnWire.lockedCode, message: summary.lockedReason ?? "Finish the lesson before this one first", source: "learn")
    }

    static func notFound(_ id: String) -> APIError {
        .server(status: 404, code: "not_found", message: "Unknown lesson \(id)", source: "learn")
    }
}
