import Charts
import SwiftUI

/// Full-screen lesson: short chart, 2 sentences, 1-tap quiz.
struct LessonView: View {
    let state: LessonViewState
    var actions: LessonActions = .noop

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                    if state.isNewConcept {
                        Label("New concept unlocked", systemImage: "sparkles")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(.tint)
                            .accessibilityIdentifier("lesson.newConcept")
                    }
                    Text(state.title)
                        .font(.largeTitle.bold())
                        .accessibilityAddTraits(.isHeader)
                    LessonChart(chart: state.chart)
                    ForEach(Array(state.sentences.enumerated()), id: \.offset) { _, sentence in
                        Text(sentence).font(.title3)
                    }
                    QuizCard(quiz: state.quiz, onAnswer: actions.onAnswer)
                }
                .padding(Theme.Spacing.l)
            }
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done", action: actions.onClose)
                        .accessibilityIdentifier("lesson.close")
                }
            }
        }
    }
}

/// Swift Charts line or bar chart with its source chip.
struct LessonChart: View {
    let chart: ChartState

    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                Text(chart.title).font(.headline)
                Chart(chart.points) { point in
                    switch chart.kind {
                    case .line:
                        LineMark(x: .value(chart.xLabel, point.x), y: .value(chart.yLabel, point.y))
                        PointMark(x: .value(chart.xLabel, point.x), y: .value(chart.yLabel, point.y))
                    case .bar:
                        BarMark(x: .value(chart.xLabel, point.label ?? String(Int(point.x))), y: .value(chart.yLabel, point.y))
                    }
                }
                .chartXAxisLabel(chart.xLabel)
                .chartYAxisLabel(chart.yLabel)
                .chartXAxis {
                    AxisMarks { value in
                        AxisGridLine()
                        AxisValueLabel {
                            if let x = value.as(Double.self) { Text(String(Int(x))) }
                            else if let s = value.as(String.self) { Text(s) }
                        }
                    }
                }
                .frame(height: 180)
                .accessibilityLabel(chart.title)
                if let source = chart.source {
                    SourceChip(source: source)
                }
            }
        }
    }
}

/// One question, 2 to 4 options, one tap.
struct QuizCard: View {
    let quiz: LessonViewState.Quiz
    let onAnswer: (Int) -> Void

    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text(quiz.question).font(.headline)
                ForEach(Array(quiz.options.enumerated()), id: \.offset) { index, option in
                    Button { onAnswer(index) } label: {
                        HStack {
                            Text(option)
                            Spacer()
                            if quiz.isAnswered && index == quiz.answerIndex {
                                Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
                            } else if quiz.selectedIndex == index {
                                Image(systemName: "xmark.circle.fill").foregroundStyle(.red)
                            }
                        }
                        .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                    }
                    .buttonStyle(.glass)
                    .disabled(quiz.isAnswered)
                    .accessibilityIdentifier("lesson.option.\(index)")
                }
                if quiz.isAnswered {
                    Text(quiz.isCorrect ? "Right!" : "Not quite. The answer is \(quiz.options[quiz.answerIndex]).")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(quiz.isCorrect ? .green : .orange)
                        .accessibilityIdentifier("lesson.feedback")
                }
            }
        }
        .sensoryFeedback(.success, trigger: quiz.isAnswered && quiz.isCorrect)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Unanswered · light") {
    LessonView(state: Fixtures.LessonScreen.unanswered)
}

#Preview("Unanswered · dark") {
    LessonView(state: Fixtures.LessonScreen.unanswered).previewDark()
}

#Preview("Unanswered · AX3") {
    LessonView(state: Fixtures.LessonScreen.unanswered).previewLargeType()
}

#Preview("Correct · light") {
    LessonView(state: Fixtures.LessonScreen.correct)
}

#Preview("Correct · dark") {
    LessonView(state: Fixtures.LessonScreen.correct).previewDark()
}

#Preview("Correct · AX3") {
    LessonView(state: Fixtures.LessonScreen.correct).previewLargeType()
}

#Preview("Wrong · light") {
    LessonView(state: Fixtures.LessonScreen.wrong)
}

#Preview("Wrong · dark") {
    LessonView(state: Fixtures.LessonScreen.wrong).previewDark()
}

#Preview("Wrong · AX3") {
    LessonView(state: Fixtures.LessonScreen.wrong).previewLargeType()
}
