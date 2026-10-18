// Draft by W9. Money Quiz, Same Decision and the final ranking (ADR 0052, 0059).
import SwiftUI

/// Countdown ring for the answer window. Reads the clock in a TimelineView; the state holds only the deadline.
struct CountdownRing: View {
    let deadline: Date?
    let duration: Double
    var size: CGFloat = 56

    var body: some View {
        TimelineView(.periodic(from: .now, by: 0.25)) { context in
            let left = max(0, deadline?.timeIntervalSince(context.date) ?? 0)
            let fraction = duration > 0 ? left / duration : 0
            ZStack {
                Circle().fill(Theme.Palette.surface)
                Circle()
                    .trim(from: 0, to: fraction)
                    .stroke(left <= 5 ? Theme.Palette.health : Theme.Palette.money, style: StrokeStyle(lineWidth: 6, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .padding(5)
                Circle().strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline)
                Text(deadline == nil ? "-" : "\(Int(left.rounded(.up)))")
                    .font(.llBodyBold)
                    .monospacedDigit()
            }
            .frame(width: size, height: size)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(deadline == nil ? L10n.tr("Time is up") : L10n.tr("\(Int(left.rounded(.up))) seconds left"))
        }
    }
}

/// Live ranking: rank, face, name, points, and a tick or cross for the last round.
struct RankingListView: View {
    let rows: [RankingRowState]
    var title = "Ranking"

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            BlockTitle(text: title).padding(.bottom, Theme.Spacing.xs)
            ForEach(Array(rows.enumerated()), id: \.element.id) { offset, row in
                if offset > 0 { RuleDivider() }
                HStack(spacing: Theme.Spacing.m) {
                    Text("\(row.rank)").font(.llLabelBold).frame(width: 16)
                    LLIconImage(LLIcon(rawValue: row.face) ?? .faceTeen, size: 32)
                    Text(row.isMe ? L10n.tr("You") : row.name)
                        .font(row.isMe ? .llBodyBold : .llBody)
                        .lineLimit(1)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    if let correct = row.lastCorrect {
                        Chip(text: correct ? L10n.tr("Right") : L10n.tr("Missed"), fill: correct ? Theme.Palette.money : Theme.Palette.other)
                    }
                    Text("\(row.score)")
                        .font(.llBodyBold)
                        .monospacedDigit()
                        .contentTransition(.numericText(value: Double(row.score)))
                        .frame(minWidth: 44, alignment: .trailing)
                }
                .frame(minHeight: Theme.minTarget)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(spoken(row))
                .accessibilityIdentifier("ranking.\(row.id)")
            }
        }
    }
}

extension RankingListView {
    fileprivate func spoken(_ row: RankingRowState) -> String {
        let name = row.isMe ? L10n.tr("You") : row.name
        switch row.lastCorrect {
        case true: return L10n.tr("\(row.rank). \(name), \(row.score) points, right last round")
        case false: return L10n.tr("\(row.rank). \(name), \(row.score) points, missed last round")
        default: return L10n.tr("\(row.rank). \(name), \(row.score) points")
        }
    }
}

/// One answer button with its mark after the reveal.
struct AnswerButton: View {
    let text: String
    let mark: AnswerMark
    var detail: String?
    let isLocked: Bool
    let identifier: String
    let action: () -> Void

    private var fill: Color {
        switch mark {
        case .none: Theme.Palette.surface
        case .picked: Theme.Palette.work
        case .correct: Theme.Palette.money
        case .wrong: Theme.Palette.health
        }
    }

    var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.m) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(text).font(.llBodyBold).fixedSize(horizontal: false, vertical: true)
                    if let detail, !detail.isEmpty {
                        Text(detail).font(.llLabel).fixedSize(horizontal: false, vertical: true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                switch mark {
                case .correct: LLIconImage(.check, size: 24)
                case .picked: Text("Yours").font(.llLabelBold)
                default: EmptyView()
                }
            }
            .foregroundStyle(mark == .none ? Theme.Palette.ink : Theme.Palette.onArea)
            .padding(.horizontal, Theme.Spacing.l)
            .padding(.vertical, Theme.Spacing.m)
            .frame(minHeight: Theme.buttonHeight)
            .inkSurface(.buttonAlt, fill: fill)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .disabled(isLocked)
        .accessibilityValue(markText)
        .accessibilityIdentifier(identifier)
    }

    private var markText: String {
        switch mark {
        case .none: ""
        case .picked: "Your answer"
        case .correct: "Right answer"
        case .wrong: "Your answer, wrong"
        }
    }
}

/// Money Quiz round: question, 2 to 4 choices, 15 s ring, reveal with Penny's line and the source, live ranking.
struct QuizView: View {
    let state: QuizViewState
    var actions: RoundActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                HStack(spacing: Theme.Spacing.m) {
                    HeaderSquareButton(kind: .close, identifier: "quiz.leave", action: actions.onLeave)
                        .accessibilityLabel("Leave the game")
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Money Quiz").llEyebrow()
                        Text(state.progressText).font(.llBodyBold).accessibilityIdentifier("quiz.progress")
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    if state.isSampleData { DemoDataBadge() }
                    CountdownRing(deadline: state.deadline, duration: state.duration)
                }
                if let connection = state.connection {
                    RoomConnectionBanner(state: connection, onRetry: actions.onReconnect)
                }
                Text(state.text)
                    .font(.llTitle)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)
                    .accessibilityIdentifier("quiz.question")
                VStack(spacing: Theme.Spacing.s) {
                    ForEach(state.choices) { choice in
                        AnswerButton(text: choice.text, mark: choice.mark, isLocked: state.isLocked, identifier: "quiz.choice.\(choice.id)") {
                            actions.onAnswer(choice.id)
                        }
                    }
                }
                if let reveal = state.reveal {
                    HStack(alignment: .top, spacing: Theme.Spacing.m) {
                        LLIconImage(.pennySmiling, size: 40)
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            Text(reveal.explanation).font(.llBody).fixedSize(horizontal: false, vertical: true)
                            SourceLine(label: reveal.sourceLabel, url: reveal.sourceURL)
                        }
                    }
                    .padding(Theme.Spacing.l)
                    .inkSurface(.hero, hero: true)
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("quiz.reveal")
                } else {
                    Text(state.statusText).font(.llLabel).foregroundStyle(Theme.Palette.muted).accessibilityIdentifier("quiz.status")
                }
                if state.reveal != nil {
                    Text(state.statusText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                RankingListView(rows: state.ranking)
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }
}

/// "Source: gov.uk · Lifetime ISA", a link when there is a URL.
struct SourceLine: View {
    let label: String
    let url: String?

    var body: some View {
        if let url, let link = URL(string: url) {
            Link(destination: link) {
                Text(L10n.tr("Source: \(label)")).font(.llLabelBold).underline()
            }
            .frame(minHeight: Theme.minTarget, alignment: .leading)
            .accessibilityIdentifier("source.link")
        } else {
            Text(L10n.tr("Source: \(label)")).font(.llLabel).foregroundStyle(Theme.Palette.muted)
        }
    }
}

/// Same Decision round: the year and what was happening, the options, the timer, then everyone's choices,
/// the game money outcome of each option, Penny's line and the ranking.
struct DecisionView: View {
    let state: DecisionViewState
    var actions: RoundActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                HStack(spacing: Theme.Spacing.m) {
                    HeaderSquareButton(kind: .close, identifier: "decision.leave", action: actions.onLeave)
                        .accessibilityLabel("Leave the game")
                    VStack(alignment: .leading, spacing: 0) {
                        Text("Same Decision").llEyebrow()
                        Text(state.yearText).font(.llTitle)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    if state.isSampleData { DemoDataBadge() }
                    CountdownRing(deadline: state.deadline, duration: state.duration)
                }
                if let connection = state.connection {
                    RoomConnectionBanner(state: connection, onRetry: actions.onReconnect)
                }
                if !state.context.isEmpty {
                    Text(state.context).font(.llBody).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
                }
                Text(state.text).font(.llTitle).fixedSize(horizontal: false, vertical: true).accessibilityAddTraits(.isHeader)
                VStack(spacing: Theme.Spacing.s) {
                    ForEach(state.options) { option in
                        AnswerButton(text: option.label, mark: option.mark, detail: detail(option), isLocked: state.isLocked, identifier: "decision.option.\(option.id)") {
                            actions.onAnswer(option.id)
                        }
                    }
                }
                if !state.isLocked, !state.options.isEmpty, let onAskPenny = actions.onAskPenny {
                    Button(action: onAskPenny) {
                        HStack(spacing: Theme.Spacing.s) {
                            PennyView(mood: .thinking, size: 28)
                            Text("Not sure? Ask Penny")
                        }
                    }
                    .buttonStyle(.text)
                    .frame(minHeight: Theme.minTarget)
                    .accessibilityIdentifier("decision.askPenny")
                }
                if let penny = state.pennyLine {
                    HStack(alignment: .top, spacing: Theme.Spacing.m) {
                        LLIconImage(.pennySmiling, size: 40)
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            Text(penny).font(.llBody).fixedSize(horizontal: false, vertical: true)
                            Text("Game money only. Not your real money.").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                    }
                    .padding(Theme.Spacing.l)
                    .inkSurface(.hero, hero: true)
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("decision.reveal")
                    if !state.missedText.isEmpty {
                        Text(state.missedText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                }
                Text(state.statusText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                RankingListView(rows: state.ranking)
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    /// After the reveal: "Game money +£300 · 25% bonus... · Ava, You".
    private func detail(_ option: DecisionViewState.Option) -> String? {
        guard let money = option.gameMoney else { return nil }
        var parts = [L10n.tr("Game money \(Money.signed(money))")]
        if !option.note.isEmpty { parts.append(option.note) }
        if !option.pickedBy.isEmpty { parts.append(L10n.tr("Picked by \(option.pickedBy.joined(separator: ", "))")) }
        return parts.joined(separator: ". ")
    }
}

/// Final ranking for Money Quiz and Same Decision.
struct GameOverView: View {
    let state: GameOverViewState
    var actions: GameOverActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: state.gameTitle, leading: HeaderSquareButton(kind: .close, identifier: "gameOver.close", action: actions.onClose)) {
                    if state.isSampleData { DemoDataBadge() }
                }
                HStack(spacing: 14) {
                    LLIconImage(.trophy, size: 64)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Final ranking").llEyebrow()
                        Text(state.winnerLine).font(.llTitle).fixedSize(horizontal: false, vertical: true)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(Theme.Spacing.l)
                .inkSurface(.hero, hero: true)
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("gameOver.winner")
                RankingListView(rows: state.ranking, title: L10n.tr("Points"))
                Button(state.isHost ? L10n.tr("New lobby, same friends") : L10n.tr("Back to Play"), action: actions.onPlayAgain)
                    .buttonStyle(.main)
                    .accessibilityIdentifier("gameOver.again")
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Quiz question · light") { QuizView(state: RoomFlowFixtures.quizQuestion) }
#Preview("Quiz question · dark") { QuizView(state: RoomFlowFixtures.quizQuestion).previewDark() }
#Preview("Quiz question · AX3") { QuizView(state: RoomFlowFixtures.quizQuestion).previewLargeType() }
#Preview("Quiz reveal · light") { QuizView(state: RoomFlowFixtures.quizReveal) }
#Preview("Quiz reveal · dark") { QuizView(state: RoomFlowFixtures.quizReveal).previewDark() }
#Preview("Decision · light") { DecisionView(state: RoomFlowFixtures.decisionOpen) }
#Preview("Decision reveal · light") { DecisionView(state: RoomFlowFixtures.decisionReveal) }
#Preview("Decision reveal · dark") { DecisionView(state: RoomFlowFixtures.decisionReveal).previewDark() }
#Preview("Decision reveal · AX3") { DecisionView(state: RoomFlowFixtures.decisionReveal).previewLargeType() }
#Preview("Game over · light") { GameOverView(state: RoomFlowFixtures.gameOver) }
#Preview("Game over · dark") { GameOverView(state: RoomFlowFixtures.gameOver).previewDark() }
