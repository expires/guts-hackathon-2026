import Foundation

// Play with friends, step 5 (ADR 0052, 0059): student paths, circles and the player's account name.
// `PlayService` hides the client. Live mode forwards to `LifelineClient`. Mock mode uses `MockPlayService`.

/// Contract types for games and circles. Nested names, so they never clash with shared typealiases.
enum PlayWire {
    typealias Options = Components.Schemas.GameOptions
    typealias Question = Components.Schemas.QuizQuestion
    typealias QuizChoice = Components.Schemas.QuizChoice
    typealias QuizReveal = Components.Schemas.QuizReveal
    typealias Prompt = Components.Schemas.DecisionPrompt
    typealias PromptOption = Components.Schemas.DecisionOption
    typealias DecisionReveal = Components.Schemas.DecisionReveal
    typealias Outcome = Components.Schemas.DecisionOutcome
    typealias PlayerChoice = Components.Schemas.PlayerChoice
    typealias Score = Components.Schemas.PlayerScore
    typealias Path = Components.Schemas.StudentPath
    typealias Student = Components.Schemas.QuickStudent
    typealias Circle = Components.Schemas.Circle
    typealias Member = Components.Schemas.CircleMember
    typealias Habits = Components.Schemas.HabitScore
    typealias HabitParts = Components.Schemas.HabitComponents
}

/// The game the host picks in the lobby.
enum RoomGameKind: String, CaseIterable, Sendable, Identifiable {
    case quiz
    case sameDecision = "same_decision"
    case sameLife = "same_life"

    var id: String { rawValue }

    var title: String {
        switch self {
        case .quiz: L10n.tr("Money Quiz")
        case .sameDecision: L10n.tr("Same Decision")
        case .sameLife: L10n.tr("Same Life")
        }
    }

    var detail: String {
        switch self {
        case .quiz: L10n.tr("Quick questions on student money. 15 seconds each.")
        case .sameDecision: L10n.tr("One money choice in real history. See what everyone picked.")
        case .sameLife: L10n.tr("Everyone lives the same student life. Who ends up best?")
        }
    }

    /// `LLIcon` raw value.
    var icon: String {
        switch self {
        case .quiz: "lesson"
        case .sameDecision: "why"
        case .sameLife: "tab-life"
        }
    }

    init?(room: Room.GamePayload?) {
        guard let raw = room?.rawValue else { return nil }
        self.init(rawValue: raw)
    }
}

/// Student paths plus the premade Quick Life students.
struct PlayPaths: Sendable, Equatable {
    var paths: [PlayWire.Path]
    var students: [PlayWire.Student]
}

protocol PlayService: Sendable {
    /// Student start paths (`GET /v1/paths`).
    func paths() async throws -> [PlayWire.Path]
    func circles() async throws -> [PlayWire.Circle]
    func createCircle(name: String) async throws -> PlayWire.Circle
    func joinCircle(code: String) async throws -> PlayWire.Circle
    func leaveCircle(id: String) async throws
    /// Your account name (`GET /v1/me` display_name). Nil when unknown; the server then names you "Player N".
    func myName() async -> String?
    /// Disk first, then network (ADR 0060). `onUpdate` runs once or twice.
    /// Paths and the 5 premade Quick Life students (`GET /v1/paths`, ADR 0064).
    func loadPaths(_ onUpdate: @escaping @MainActor @Sendable (PlayPaths) -> Void) async throws
    func quickStudents() async throws -> [PlayWire.Student]
    func loadCircles(_ onUpdate: @escaping @MainActor @Sendable ([PlayWire.Circle]) -> Void) async throws
}

extension PlayService {
    /// No cache: one network call.
    func loadPaths(_ onUpdate: @escaping @MainActor @Sendable (PlayPaths) -> Void) async throws {
        let value = PlayPaths(paths: try await paths(), students: (try? await quickStudents()) ?? [])
        await onUpdate(value)
    }

    func loadCircles(_ onUpdate: @escaping @MainActor @Sendable ([PlayWire.Circle]) -> Void) async throws {
        let value = try await circles()
        await onUpdate(value)
    }
}

/// Live mode: forwards to `LifelineClient`.
struct ClientPlayService: PlayService {
    let client: any LifelineClient

    func paths() async throws -> [PlayWire.Path] { try await client.listPaths().paths }
    func circles() async throws -> [PlayWire.Circle] { try await client.listCircles() }
    func createCircle(name: String) async throws -> PlayWire.Circle { try await client.createCircle(name: name) }
    func joinCircle(code: String) async throws -> PlayWire.Circle { try await client.joinCircle(code: code) }
    func leaveCircle(id: String) async throws { try await client.leaveCircle(id: id) }
    func quickStudents() async throws -> [PlayWire.Student] { try await client.listPaths().quickStudents ?? [] }

    func loadPaths(_ onUpdate: @escaping @MainActor @Sendable (PlayPaths) -> Void) async throws {
        try await client.load(CachedOps.paths) { response in
            onUpdate(PlayPaths(paths: response.paths, students: response.quickStudents ?? []))
        }
    }

    func loadCircles(_ onUpdate: @escaping @MainActor @Sendable ([PlayWire.Circle]) -> Void) async throws {
        try await client.load(CachedOps.circles, onUpdate: onUpdate)
    }

    func myName() async -> String? {
        guard let name = try? await client.getMe().displayName, !name.isEmpty else { return nil }
        return name
    }
}

@MainActor
enum PlayServiceFactory {
    static func make(client: any LifelineClient) -> any PlayService {
        client.kind == .mock ? MockPlayService() : ClientPlayService(client: client)
    }
}

/// Mock paths and circles. Every number is a 0 to 100 ratio. No amounts (ADR 0052 privacy rule).
actor MockPlayService: PlayService {
    private var stored: [PlayWire.Circle]
    private var nextID = 2

    init(circles: [PlayWire.Circle] = MockPlayData.circles) {
        stored = circles
    }

    nonisolated func paths() async throws -> [PlayWire.Path] { MockPlayData.paths }
    nonisolated func quickStudents() async throws -> [PlayWire.Student] { MockPlayData.quickStudents }
    func circles() async throws -> [PlayWire.Circle] { stored }

    func createCircle(name: String) async throws -> PlayWire.Circle {
        let circle = PlayWire.Circle(
            id: "c\(nextID)", name: name, code: String(format: "CIRC%02d", nextID),
            members: [MockPlayData.you], recap: nil, recapWeek: nil
        )
        nextID += 1
        stored.append(circle)
        return circle
    }

    func joinCircle(code: String) async throws -> PlayWire.Circle {
        if let circle = stored.first(where: { $0.code == code }) { return circle }
        guard CircleCode.isValid(code) else {
            throw APIError.server(status: 422, code: "validation_error", message: "code: 6 letters or digits", source: "mock")
        }
        var circle = MockPlayData.circles[0]
        circle.id = "c\(nextID)"
        circle.code = code
        circle.name = "Circle \(code)"
        nextID += 1
        stored.append(circle)
        return circle
    }

    func leaveCircle(id: String) async throws {
        stored.removeAll { $0.id == id }
    }

    nonisolated func myName() async -> String? { "Ash" }
}

/// Mock data for paths, circles, quiz questions and decisions. Facts are real UK rules with their official source.
enum MockPlayData {
    static let paths: [PlayWire.Path] = [
        .init(id: "uni", title: "University", description: "Three-year degree with a Plan 5 student loan.", startAge: 18, quick: true),
        .init(id: "apprentice", title: "Apprenticeship", description: "Earn while you learn. No tuition loan.", startAge: 18, quick: true),
        .init(id: "job18", title: "Job at 18", description: "Start full-time work straight after school.", startAge: 18, quick: true),
        .init(id: "gap_year", title: "Gap year", description: "Work and travel for a year, then decide.", startAge: 18, quick: false),
        .init(id: "masters", title: "Master's degree", description: "A degree, then a one-year master's with a postgraduate loan.", startAge: 21, quick: false),
    ]

    /// The server's five premade Quick Life students (W3, lifeline_sim/paths.py).
    static let quickStudents: [PlayWire.Student] = [
        .init(id: "qs-priya", name: "Priya", pathId: "uni", description: "University in Birmingham, paid with the full student loan."),
        .init(id: "qs-amara", name: "Amara", pathId: "uni", description: "University in London with a £2,000 a year bursary."),
        .init(id: "qs-jordan", name: "Jordan", pathId: "apprentice", description: "Electrician apprentice in Manchester. Paid to train."),
        .init(id: "qs-kai", name: "Kai", pathId: "job18", description: "Starts work at 18 in Leeds and lives at home."),
        .init(id: "qs-maya", name: "Maya", pathId: "gap_year", description: "Works a gap year in Bristol, then goes to university."),
    ]

    static func habits(_ values: [Int], overall: Int) -> PlayWire.Habits {
        .init(
            components: .init(
                savingsRate: values[0], monthsOfCover: values[1], spendStability: values[2],
                discretionaryShare: values[3], subscriptionCreep: values[4], debtPressure: values[5]
            ),
            overall: overall
        )
    }

    static let you = PlayWire.Member(id: "m1", name: "Ash", habits: habits([22, 35, 61, 40, 18, 30], overall: 58), improvement: 6, rank: 2, isYou: true)

    static let circles: [PlayWire.Circle] = [
        .init(
            id: "c1", name: "Flat 4B", code: "FLAT4B",
            members: [
                .init(id: "m2", name: "Ava", habits: habits([30, 52, 70, 33, 10, 12], overall: 71), improvement: 9, rank: 1, isYou: false),
                you,
                .init(id: "m3", name: "Tom", habits: habits([12, 20, 48, 55, 26, 41], overall: 44), improvement: 2, rank: 3, isYou: false),
                .init(id: "m4", name: "Jas", habits: habits([18, 28, 66, 38, 15, 22], overall: 60), improvement: -3, rank: 4, isYou: false),
            ],
            recap: "Flat 4B saved a bigger share this week. Ava is most improved. Tom's subscriptions crept up a little.",
            recapWeek: "2026-W42"
        ),
    ]

    static let questions: [PlayWire.Question] = [
        .init(
            id: "q-plan5-rate", index: 0, total: 6,
            text: "On a Plan 5 student loan, what share of your income above the threshold do you repay?",
            choices: [.init(id: "a", text: "3%"), .init(id: "b", text: "6%"), .init(id: "c", text: "9%"), .init(id: "d", text: "12%")],
            answerMs: 15_000, sourceLabel: "gov.uk · Repaying your student loan", sourceUrl: "https://www.gov.uk/repaying-your-student-loan"
        ),
        .init(
            id: "q-plan5-threshold", index: 1, total: 6,
            text: "You start repaying a Plan 5 student loan when your yearly income goes over…",
            choices: [.init(id: "a", text: "£12,570"), .init(id: "b", text: "£25,000"), .init(id: "c", text: "£40,000")],
            answerMs: 15_000, sourceLabel: "gov.uk · Repaying your student loan", sourceUrl: "https://www.gov.uk/repaying-your-student-loan/what-you-pay"
        ),
        .init(
            id: "q-lisa-bonus", index: 2, total: 6,
            text: "The government adds a bonus to a Lifetime ISA. How big is it?",
            choices: [.init(id: "a", text: "10% of what you pay in"), .init(id: "b", text: "25% of what you pay in"), .init(id: "c", text: "50% of what you pay in")],
            answerMs: 15_000, sourceLabel: "gov.uk · Lifetime ISA", sourceUrl: "https://www.gov.uk/lifetime-isa"
        ),
        .init(
            id: "q-lisa-limit", index: 3, total: 6,
            text: "What is the most you can pay into a Lifetime ISA each tax year?",
            choices: [.init(id: "a", text: "£1,000"), .init(id: "b", text: "£4,000"), .init(id: "c", text: "£20,000")],
            answerMs: 15_000, sourceLabel: "gov.uk · Lifetime ISA", sourceUrl: "https://www.gov.uk/lifetime-isa"
        ),
        .init(
            id: "q-personal-allowance", index: 4, total: 6,
            text: "How much can most people earn in a year before they pay income tax?",
            choices: [.init(id: "a", text: "£10,000"), .init(id: "b", text: "£12,570"), .init(id: "c", text: "£15,000"), .init(id: "d", text: "£25,000")],
            answerMs: 15_000, sourceLabel: "gov.uk · Income Tax rates and Personal Allowances", sourceUrl: "https://www.gov.uk/income-tax-rates"
        ),
        .init(
            id: "q-isa-allowance", index: 5, total: 6,
            text: "How much can you put into ISAs in total each tax year?",
            choices: [.init(id: "a", text: "£4,000"), .init(id: "b", text: "£12,570"), .init(id: "c", text: "£20,000")],
            answerMs: 15_000, sourceLabel: "gov.uk · Individual Savings Accounts", sourceUrl: "https://www.gov.uk/individual-savings-accounts"
        ),
    ]

    /// Correct choice and Penny's one line per question id.
    static let answers: [String: (correct: String, line: String)] = [
        "q-plan5-rate": ("c", "You repay 9% of what you earn above the threshold, not 9% of all your pay."),
        "q-plan5-threshold": ("b", "Below £25,000 a year you repay nothing on Plan 5."),
        "q-lisa-bonus": ("b", "Put in £4,000 and the government adds up to £1,000."),
        "q-lisa-limit": ("b", "£4,000 a year, and it counts towards your £20,000 ISA allowance."),
        "q-personal-allowance": ("b", "The first £12,570 is your Personal Allowance for most people."),
        "q-isa-allowance": ("c", "£20,000 across all your ISAs in one tax year."),
    ]

    static let prompts: [PlayWire.Prompt] = [
        .init(
            id: "d-2022-summer", year: 2022,
            context: "In 2022 the Bank of England raised Bank Rate from 0.25% to 3.5%, and prices rose fast.",
            text: "Your summer job paid you £1,200. What do you do with it?",
            options: [
                .init(id: "save", label: "Easy-access savings"),
                .init(id: "klarna", label: "Clear my Klarna balance"),
                .init(id: "festival", label: "Festival and new trainers"),
                .init(id: "lisa", label: "Lifetime ISA"),
            ],
            answerMs: 20_000
        ),
        .init(
            id: "d-2008-crisis", year: 2008,
            context: "In 2008 banks failed around the world, and Bank Rate fell from 5% to 2% by December.",
            text: "Your bank offers a 2-year fixed saver. Do you lock your £2,000 away?",
            options: [
                .init(id: "fix", label: "Fix for 2 years"),
                .init(id: "easy", label: "Keep it easy access"),
                .init(id: "spend", label: "Spend it now"),
            ],
            answerMs: 20_000
        ),
    ]

    /// Game money outcomes per prompt. Simulated, never a player's real money.
    static let outcomes: [String: (outcomes: [PlayWire.Outcome], line: String, best: String)] = [
        "d-2022-summer": (
            [
                .init(optionId: "save", gameMoneyChange: 36, note: "Savings rates rose through the year."),
                .init(optionId: "klarna", gameMoneyChange: 60, note: "No missed payments, no late fees."),
                .init(optionId: "festival", gameMoneyChange: -1_200, note: "Great weekend. Money gone."),
                .init(optionId: "lisa", gameMoneyChange: 300, note: "25% bonus, locked until a first home or 60."),
            ],
            "The Lifetime ISA bonus beat every savings rate that year, but only if you can leave it alone.",
            "lisa"
        ),
        "d-2008-crisis": (
            [
                .init(optionId: "fix", gameMoneyChange: 180, note: "You locked in a rate before the cuts."),
                .init(optionId: "easy", gameMoneyChange: 40, note: "Your rate fell with every cut."),
                .init(optionId: "spend", gameMoneyChange: -2_000, note: "Nothing left for later."),
            ],
            "When rates are about to fall, fixing early keeps the higher rate.",
            "fix"
        ),
    ]
}
