import Foundation

/// Pure mapping for the friends games and Circles. Fixtures and tests call it directly.
@MainActor
enum GameMapping {
    /// Computed, so a language change shows at once.
    static var topics: [GamePickerViewState.Option] {
        [
            .init(id: "mixed", label: L10n.tr("Mixed")),
            .init(id: "student_finance", label: L10n.tr("Student finance")),
            .init(id: "saving", label: L10n.tr("Saving")),
            .init(id: "debt", label: L10n.tr("Debt")),
            .init(id: "tax", label: L10n.tr("Tax")),
        ]
    }

    // MARK: Lobby game card

    static func gameCard(room: Room, paths: [PlayWire.Path], students: [PlayWire.Student] = []) -> RoomGameCard? {
        guard let kind = RoomGameKind(room: room.game) else { return nil }
        let options = room.options
        let detail: String
        switch kind {
        case .quiz:
            let topic = topics.first { $0.id == options?.topic?.rawValue }?.label ?? L10n.tr("Mixed")
            detail = L10n.tr("\(options?.questions ?? 8) questions · \(topic)")
        case .sameDecision:
            detail = options?.startYear.map { L10n.tr("History from \(String($0))") } ?? L10n.tr("History from a real year")
        case .sameLife:
            let path = paths.first { $0.id == options?.pathId }?.title ?? L10n.tr("Student path")
            if options?.quick ?? true {
                let student = students.first { $0.id == options?.quickStudentId }?.name
                detail = student.map { L10n.tr("Quick Life, ages 18 to 25 · everyone plays \($0)") }
                    ?? L10n.tr("Quick Life, ages 18 to 25 · \(path)")
            } else {
                detail = L10n.tr("\(path) · Full life")
            }
        }
        return RoomGameCard(title: kind.title, detail: detail, icon: kind.icon)
    }

    // MARK: Picker

    struct Draft: Equatable, Sendable {
        var game: RoomGameKind = .quiz
        var questions = 8
        var topic = "mixed"
        var pathID: String?
        var quickStudentID: String?
        var quick = true
        var startYear = 2022

        /// The chosen student's path, set with the student.
        var studentPathID: String?

        var options: PlayWire.Options {
            switch game {
            case .quiz:
                .init(questions: questions, topic: PlayWire.Options.TopicPayload(rawValue: topic) ?? .mixed)
            case .sameDecision:
                .init(startYear: startYear)
            case .sameLife:
                quick
                    ? .init(pathId: studentPathID ?? pathID, quick: true, quickStudentId: quickStudentID, startYear: startYear)
                    : .init(pathId: pathID, quick: false, startYear: startYear)
            }
        }
    }

    static func picker(draft: Draft, paths: [PlayWire.Path], students: [PlayWire.Student] = [], pathsPhase: LoadPhase) -> GamePickerViewState {
        let shown = paths.filter { !draft.quick || $0.quick }
        let needsPath = draft.game == .sameLife
        // Quick Life with premade students: pick a student. Without them (older server), pick a path.
        let usesStudents = needsPath && draft.quick && !students.isEmpty
        let ready = usesStudents
            ? students.contains { $0.id == draft.quickStudentID }
            : (draft.pathID != nil && shown.contains { $0.id == draft.pathID })
        return GamePickerViewState(
            games: RoomGameKind.allCases.map { .init(id: $0.rawValue, label: $0.title, detail: $0.detail, icon: $0.icon) },
            selectedGame: draft.game.rawValue,
            questions: draft.questions,
            topics: topics,
            topic: draft.topic,
            paths: shown.map { .init(id: $0.id, label: $0.title, detail: $0.description) },
            pathID: draft.pathID,
            pathsPhase: pathsPhase,
            students: draft.quick ? students.map { student in
                .init(id: student.id, label: student.name, detail: student.description, icon: LLIcon.face(emoji: nil).rawValue)
            } : [],
            studentID: draft.quickStudentID,
            quick: draft.quick,
            startYear: draft.startYear,
            minYear: 1990,
            maxYear: 2026,
            confirmTitle: L10n.tr("Pick \(draft.game.title)"),
            canConfirm: !needsPath || ready
        )
    }

    // MARK: Ranking

    static func ranking(_ scores: [PlayWire.Score], room: Room?, myID: String?) -> [RankingRowState] {
        let seats = Dictionary((room?.players ?? []).enumerated().map { ($1.id, $0) }, uniquingKeysWith: { first, _ in first })
        return scores.sorted { $0.rank < $1.rank }.map { score in
            RankingRowState(
                id: score.playerId, rank: score.rank, name: score.name, score: score.score,
                isMe: score.playerId == myID, lastCorrect: score.lastCorrect,
                face: RoomMapping.face(seat: seats[score.playerId] ?? 0)
            )
        }
    }

    /// Before the first reveal: everyone at 0, in seat order.
    static func startingRanking(room: Room, myID: String?) -> [RankingRowState] {
        room.players.enumerated().map { seat, player in
            .init(id: player.id, rank: seat + 1, name: player.name, score: 0, isMe: player.id == myID, lastCorrect: nil, face: RoomMapping.face(seat: seat))
        }
    }

    private static func waitingText(room: Room, answered: Bool) -> String {
        guard answered else { return L10n.tr("Pick an answer") }
        let others = room.players.filter { $0.connected != false }.count - 1
        return others <= 0 ? L10n.tr("Answered") : L10n.tr("Answered. Waiting for the others.")
    }

    // MARK: Money Quiz

    static func quiz(
        question: PlayWire.Question?,
        reveal: PlayWire.QuizReveal?,
        myAnswer: String?,
        startedAt: Date?,
        ranking: [PlayWire.Score],
        room: Room,
        myID: String?,
        link: RoomSession.Link,
        isSampleData: Bool
    ) -> QuizViewState {
        let rows = ranking.isEmpty ? startingRanking(room: room, myID: myID) : self.ranking(ranking, room: room, myID: myID)
        guard let question else {
            return QuizViewState(
                progressText: L10n.tr("Money Quiz"), text: L10n.tr("Get ready. The first question is coming."), choices: [],
                deadline: nil, duration: 15, isLocked: true, reveal: nil, statusText: L10n.tr("Waiting for the first question"),
                ranking: rows, isSampleData: isSampleData, connection: RoomMapping.connection(link)
            )
        }
        let duration = Double(question.answerMs ?? 15_000) / 1_000
        let choices = question.choices.map { choice in
            QuizViewState.Choice(id: choice.id, text: choice.text, mark: mark(choice.id, mine: myAnswer, correct: reveal?.correctChoiceId))
        }
        return QuizViewState(
            progressText: L10n.tr("Question \(question.index + 1) of \(question.total)"),
            text: question.text,
            choices: choices,
            deadline: reveal == nil ? startedAt.map { $0.addingTimeInterval(duration) } : nil,
            duration: duration,
            isLocked: myAnswer != nil || reveal != nil,
            reveal: reveal.map { .init(explanation: $0.explanation, sourceLabel: $0.sourceLabel, sourceURL: $0.sourceUrl) },
            statusText: reveal == nil
                ? waitingText(room: room, answered: myAnswer != nil)
                : (question.index + 1 < question.total ? L10n.tr("Next question soon") : L10n.tr("Last question. Final ranking soon.")),
            ranking: rows,
            isSampleData: isSampleData,
            connection: RoomMapping.connection(link)
        )
    }

    static func mark(_ id: String, mine: String?, correct: String?) -> AnswerMark {
        guard let correct else { return id == mine ? .picked : .none }
        if id == correct { return .correct }
        return id == mine ? .wrong : .none
    }

    // MARK: Same Decision

    static func decision(
        prompt: PlayWire.Prompt?,
        reveal: PlayWire.DecisionReveal?,
        myAnswer: String?,
        startedAt: Date?,
        ranking: [PlayWire.Score],
        room: Room,
        myID: String?,
        link: RoomSession.Link,
        isSampleData: Bool
    ) -> DecisionViewState {
        let rows = ranking.isEmpty ? startingRanking(room: room, myID: myID) : self.ranking(ranking, room: room, myID: myID)
        guard let prompt else {
            return DecisionViewState(
                yearText: "", context: "", text: L10n.tr("Get ready. The decision is coming."), options: [],
                deadline: nil, duration: 20, isLocked: true, pennyLine: nil, missedText: "",
                statusText: L10n.tr("Waiting for the decision"), ranking: rows, isSampleData: isSampleData,
                connection: RoomMapping.connection(link)
            )
        }
        let duration = Double(prompt.answerMs ?? 20_000) / 1_000
        let outcomes = Dictionary((reveal?.outcomes ?? []).map { ($0.optionId, $0) }, uniquingKeysWith: { first, _ in first })
        let best = reveal?.outcomes.max { $0.gameMoneyChange < $1.gameMoneyChange }?.optionId
        let options = prompt.options.map { option in
            let pickers = (reveal?.choices ?? []).filter { $0.optionId == option.id }.map { $0.playerId == myID ? L10n.tr("You") : $0.name }
            return DecisionViewState.Option(
                id: option.id, label: option.label,
                mark: mark(option.id, mine: myAnswer, correct: reveal == nil ? nil : best),
                pickedBy: pickers,
                gameMoney: outcomes[option.id]?.gameMoneyChange,
                note: outcomes[option.id]?.note ?? ""
            )
        }
        let missed = (reveal?.choices ?? []).filter { $0.optionId == nil }.map { $0.playerId == myID ? L10n.tr("You") : $0.name }
        return DecisionViewState(
            yearText: String(prompt.year),
            context: prompt.context,
            text: prompt.text,
            options: options,
            deadline: reveal == nil ? startedAt.map { $0.addingTimeInterval(duration) } : nil,
            duration: duration,
            isLocked: myAnswer != nil || reveal != nil,
            pennyLine: reveal?.pennyLine,
            missedText: missed.isEmpty ? "" : L10n.tr("No answer in time: \(missed.joined(separator: ", "))"),
            statusText: reveal == nil ? waitingText(room: room, answered: myAnswer != nil) : L10n.tr("Next decision soon"),
            ranking: rows,
            isSampleData: isSampleData,
            connection: RoomMapping.connection(link)
        )
    }

    // MARK: Game over

    static func gameOver(room: Room, ranking: [PlayWire.Score], myID: String?, isSampleData: Bool) -> GameOverViewState {
        let rows = ranking.isEmpty ? startingRanking(room: room, myID: myID) : self.ranking(ranking, room: room, myID: myID)
        let winner = rows.first
        let isHost = room.players.first { $0.id == myID }?.isHost ?? false
        return GameOverViewState(
            gameTitle: RoomGameKind(room: room.game)?.title ?? L10n.tr("Game"),
            winnerLine: winner.map { $0.isMe ? L10n.tr("You win with \($0.score) points") : L10n.tr("\($0.name) wins with \($0.score) points") } ?? "",
            ranking: rows,
            isHost: isHost,
            isSampleData: isSampleData
        )
    }

    // MARK: Habits and Quick Life

    static func habits(_ parts: PlayWire.HabitParts?) -> [QuickLifeCardState.Habit] {
        guard let parts else { return [] }
        let rows: [(String, String, Int?)] = [
            ("savings_rate", L10n.tr("Saving rate"), parts.savingsRate),
            ("months_of_cover", L10n.tr("Months of cover"), parts.monthsOfCover),
            ("spend_stability", L10n.tr("Steady spending"), parts.spendStability),
            ("discretionary_share", L10n.tr("Spending on extras"), parts.discretionaryShare),
            ("subscription_creep", L10n.tr("Subscription creep"), parts.subscriptionCreep),
            ("debt_pressure", L10n.tr("Debt pressure"), parts.debtPressure),
        ]
        return rows.compactMap { id, label, value in value.map { .init(id: id, label: label, value: $0) } }
    }

    static func quickLife(life: Life, summary: LifeSummary?, pathTitle: String?) -> QuickLifeCardState {
        QuickLifeCardState(
            title: pathTitle.map { L10n.tr("Your Quick Life · \($0)") } ?? L10n.tr("Your Quick Life"),
            index: summary?.finalIndex ?? life.index.value,
            gameNetWorth: summary?.netWorth ?? life.finances.netWorth,
            ribbons: summary?.ribbons.count ?? life.ribbons.count,
            habitOverall: summary?.habitScore?.overall,
            habits: habits(summary?.habitScore?.components)
        )
    }

    // MARK: Circles

    static func circles(
        _ circles: [PlayWire.Circle],
        phase: LoadPhase,
        selectedID: String?,
        newName: String,
        joinCode: String,
        busyText: String?,
        errorText: String?,
        isSampleData: Bool
    ) -> CirclesViewState {
        CirclesViewState(
            phase: phase,
            circles: circles.map { circle in
                let members = circle.members
                    .sorted { ($0.rank ?? Int.max, $0.name) < ($1.rank ?? Int.max, $1.name) }
                    .enumerated()
                    .map { seat, member in
                        CirclesViewState.Member(
                            id: member.id, name: member.isYou == true ? L10n.tr("You") : member.name, isYou: member.isYou == true,
                            rank: member.rank,
                            improvementText: member.improvement.map { $0 >= 0 ? L10n.tr("+\($0) points") : L10n.tr("\($0) points") } ?? "",
                            improvement: member.improvement,
                            overall: member.habits.overall,
                            habits: habits(member.habits.components),
                            face: RoomMapping.face(seat: seat)
                        )
                    }
                return CirclesViewState.CircleRow(
                    id: circle.id, name: circle.name, code: circle.code,
                    detail: members.count == 1 ? L10n.tr("1 member") : L10n.tr("\(members.count) members"),
                    members: members,
                    recap: circle.recap,
                    recapWeek: circle.recapWeek.flatMap { $0.split(separator: "W").last.map { L10n.tr("Week \(Int($0) ?? 0)") } }
                )
            },
            selectedID: selectedID,
            newName: newName,
            canCreate: !newName.trimmingCharacters(in: .whitespaces).isEmpty && busyText == nil,
            joinCode: joinCode,
            canJoin: CircleCode.isValid(joinCode) && busyText == nil,
            busyText: busyText,
            errorText: errorText,
            isSampleData: isSampleData
        )
    }
}
