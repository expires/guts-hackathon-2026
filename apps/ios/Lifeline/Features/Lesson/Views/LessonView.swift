// Rebuilt for ADR 0026 (Life-Lesson.dc.html) by W7.
import Charts
import SwiftUI

/// Full-screen lesson after a key moment: hero change, chart, concept card, 1-tap quiz.
struct LessonView: View {
    let state: LessonViewState
    var actions: LessonActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                HStack {
                    OutlineTag(text: "Lesson", icon: .lesson, eyebrow: true)
                    if state.isSampleData { DemoDataBadge() }
                    Spacer()
                    HeaderSquareButton(kind: .close, identifier: "lesson.close", action: actions.onClose)
                }
                VStack(alignment: .leading, spacing: 6) {
                    if let eyebrow = state.eyebrow {
                        Text(eyebrow)
                            .font(.llLabelBold)
                            .foregroundStyle(Theme.Palette.muted)
                    }
                    Text(state.title)
                        .font(.llTitle)
                        .accessibilityAddTraits(.isHeader)
                }
                if let hero = state.heroLine {
                    ViewThatFits(in: .horizontal) {
                        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.s) {
                            Text(hero).font(.llHero).lineLimit(1)
                            Text(state.heroCaption).font(.llLabel)
                        }
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            Text(hero).font(.llHero).minimumScaleFactor(0.6)
                            Text(state.heroCaption).font(.llLabel)
                        }
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("lesson.hero")
                }
                if !state.chart.points.isEmpty {
                    LessonChart(chart: state.chart)
                }
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    if let change = state.changeSentence {
                        Text(change).font(.llBodyBold)
                    }
                    if state.sentences.count > 1 {
                        Text(state.sentences[1]).font(.llBody)
                    }
                    if let personal = state.personal {
                        Text(personal).font(.llBody).accessibilityIdentifier("lesson.personal")
                    }
                }
                conceptCard
                QuizCard(quiz: state.quiz, onAnswer: actions.onAnswer)
                VStack(spacing: Theme.Spacing.s) {
                    if state.canRewind {
                        Button(action: actions.onRewind) {
                            HStack(spacing: 10) {
                                LLIconImage(.rewind, size: 24)
                                Text("Rewind and try again")
                            }
                        }
                        .buttonStyle(.main)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .accessibilityIdentifier("lesson.rewind")
                    }
                    Button("Keep living", action: actions.onClose)
                        .buttonStyle(.second)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .accessibilityIdentifier("lesson.keepLiving")
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    private var conceptCard: some View {
        InkCard(shape: .hero, hero: true) {
            HStack(spacing: Theme.Spacing.m) {
                PennyView(mood: .happy, size: 48)
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    Text(state.conceptLine)
                        .font(.llLabelBold)
                        .accessibilityIdentifier(state.isNewConcept ? "lesson.newConcept" : "lesson.concept")
                    if let first = state.sentences.first {
                        Text(first).font(.llBody)
                    }
                }
            }
        }
        .accessibilityElement(children: .combine)
    }
}

/// Chart of the lesson's data: ink line, area accent on the first value, coral dot on the last value.
struct LessonChart: View {
    let chart: ChartState

    private var yDomain: ClosedRange<Double> {
        let values = chart.points.map(\.y)
        let low = min(0, values.min() ?? 0)
        let high = max(values.max() ?? 1, low + 1)
        return low ... high * 1.1
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(chart.title).font(.llLabelBold)
            Chart {
                ForEach(chart.points) { point in
                    switch chart.kind {
                    case .line:
                        LineMark(x: .value(chart.xLabel, point.x), y: .value(chart.yLabel, point.y))
                            .foregroundStyle(Theme.Palette.ink)
                            .lineStyle(StrokeStyle(lineWidth: 3, lineCap: .round, lineJoin: .round))
                    case .bar:
                        BarMark(x: .value(chart.xLabel, point.label ?? String(Int(point.x))), y: .value(chart.yLabel, point.y))
                            .foregroundStyle(Theme.Palette.home)
                    }
                }
                if chart.kind == .line, let first = chart.points.first {
                    PointMark(x: .value(chart.xLabel, first.x), y: .value(chart.yLabel, first.y))
                        .symbol { dot(Theme.Palette.home) }
                }
                if chart.kind == .line, chart.points.count > 1, let last = chart.points.last {
                    PointMark(x: .value(chart.xLabel, last.x), y: .value(chart.yLabel, last.y))
                        .symbol { dot(Theme.Palette.health) }
                }
            }
            .chartYScale(domain: yDomain)
            .chartXScale(domain: .automatic(includesZero: false))
            .chartXAxis {
                AxisMarks(values: chart.kind == .line ? .automatic(desiredCount: min(4, max(2, chart.points.count))) : .automatic) { value in
                    AxisValueLabel {
                        if let x = value.as(Double.self) { Text(String(Int(x))) } else if let s = value.as(String.self) { Text(s) }
                    }
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                }
            }
            .chartYAxis {
                AxisMarks(position: .leading, values: .automatic(desiredCount: 3)) { value in
                    AxisGridLine(stroke: StrokeStyle(lineWidth: 1.5)).foregroundStyle(Theme.Palette.rule)
                    AxisValueLabel {
                        if let y = value.as(Double.self) { Text(LessonViewModel.format(y, unit: chart.yLabel)) }
                    }
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                }
            }
            .frame(height: 150)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(chart.title)
            .accessibilityValue(chart.points.map { "\($0.label ?? String(Int($0.x))): \(LessonViewModel.format($0.y, unit: chart.yLabel))" }.joined(separator: ", "))
            if let source = chart.source {
                SourceChip(source: source)
            }
        }
        .padding(.horizontal, Theme.Spacing.m)
        .padding(.top, 14)
        .padding(.bottom, 10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(HandCut((18, 24, 16, 22), (22, 16, 24, 18)))
    }

    private func dot(_ color: Color) -> some View {
        Circle()
            .fill(color)
            .stroke(Theme.Palette.ink, lineWidth: 2.5)
            .frame(width: 12, height: 12)
    }
}

/// One question, 2 to 4 options, one tap.
struct QuizCard: View {
    let quiz: LessonViewState.Quiz
    let onAnswer: (Int) -> Void

    var body: some View {
        InkCard(shape: .cardAlt) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text(quiz.question).font(.llBodyBold)
                ForEach(Array(quiz.options.enumerated()), id: \.offset) { index, option in
                    Button { onAnswer(index) } label: {
                        HStack {
                            Text(option)
                            Spacer()
                            if quiz.isAnswered && index == quiz.answerIndex {
                                LLIconImage(.check)
                            }
                        }
                    }
                    .buttonStyle(QuizOptionStyle(fill: fill(for: index)))
                    .disabled(quiz.isAnswered)
                    .accessibilityIdentifier("lesson.option.\(index)")
                }
                if quiz.isAnswered {
                    Text(quiz.isCorrect ? "Right!" : "Not quite. The answer is \(quiz.options[quiz.answerIndex]).")
                        .font(.llBodyBold)
                        .accessibilityIdentifier("lesson.feedback")
                }
            }
        }
        .sensoryFeedback(.success, trigger: quiz.isAnswered && quiz.isCorrect)
    }

    private func fill(for index: Int) -> Color {
        guard quiz.isAnswered else { return Theme.Palette.surface }
        if index == quiz.answerIndex { return Theme.Palette.money }
        if index == quiz.selectedIndex { return Theme.Palette.health }
        return Theme.Palette.surface
    }
}

/// Quiz option: 44 pt, 2 pt outline, area fill after the answer. Disabled options keep full opacity.
private struct QuizOptionStyle: ButtonStyle {
    let fill: Color

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.llBodyBold)
            .foregroundStyle(fill == Theme.Palette.surface ? Theme.Palette.ink : Theme.Palette.onArea)
            .padding(.horizontal, Theme.Spacing.m)
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .inkSurface(.buttonThird, fill: fill, lineWidth: Theme.chipOutline)
            .offset(x: configuration.isPressed ? 2 : 0, y: configuration.isPressed ? 2 : 0)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Unanswered · light") { LessonView(state: LessonFixtures.inLife) }
#Preview("Unanswered · dark") { LessonView(state: LessonFixtures.inLife).previewDark() }
#Preview("Unanswered · AX3") { LessonView(state: LessonFixtures.inLife).previewLargeType() }
#Preview("Rate shock · light") { LessonView(state: LessonFixtures.rateShock) }
#Preview("Rate shock · dark") { LessonView(state: LessonFixtures.rateShock).previewDark() }
#Preview("Rate shock · AX3") { LessonView(state: LessonFixtures.rateShock).previewLargeType() }
#Preview("Correct · light") { LessonView(state: Fixtures.LessonScreen.correct) }
#Preview("Correct · dark") { LessonView(state: Fixtures.LessonScreen.correct).previewDark() }
#Preview("Correct · AX3") { LessonView(state: Fixtures.LessonScreen.correct).previewLargeType() }
#Preview("Wrong · light") { LessonView(state: Fixtures.LessonScreen.wrong) }
#Preview("Wrong · dark") { LessonView(state: Fixtures.LessonScreen.wrong).previewDark() }
#Preview("Wrong · AX3") { LessonView(state: Fixtures.LessonScreen.wrong).previewLargeType() }
