// Draft by W9 (ADR 0068 Learn). Owned by the UI owner from creation.
import SwiftUI

/// One Learn lesson: cards one at a time, the real number with its source, a 3-question quiz, the result.
struct LearnLessonView: View {
    let state: LearnLessonViewState
    var actions: LearnLessonActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                header
                switch state.phase {
                case .loading:
                    SkeletonCard(lines: 3)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                    Button(L10n.tr("Back to the path"), action: actions.onClose)
                        .buttonStyle(.second)
                        .accessibilityIdentifier("learn.lesson.backToPath")
                case .ready:
                    progress
                    page
                        .id(state.step)
                        .transition(reduceMotion ? .opacity : .push(from: .trailing))
                    if let error = state.errorText {
                        Text(error).font(.llBodyBold).foregroundStyle(Theme.Palette.health)
                            .accessibilityIdentifier("learn.lesson.error")
                    }
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.xs)
            .padding(.bottom, Theme.Spacing.xl)
            .animation(reduceMotion ? nil : Motion.standard, value: state.step)
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            if state.phase == .ready { bottomBar }
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    // MARK: Header

    private var header: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            HeaderSquareButton(kind: .close, identifier: "learn.lesson.close", action: actions.onClose)
            VStack(alignment: .leading, spacing: 2) {
                if let unit = state.unitTitle {
                    Text(unit).llEyebrow().foregroundStyle(Theme.Palette.muted)
                }
                Text(state.title)
                    .font(.llScreenHeader)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var progress: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            // One segment per card, plus one for the quiz (PENNY_V3_BUILD E4).
            HStack(spacing: 4) {
                ForEach(0..<state.progressSegments, id: \.self) { index in
                    Capsule()
                        .fill(index < state.filledSegments ? Theme.Palette.ink : Theme.Palette.rule)
                        .frame(height: 6)
                }
            }
            Text(state.stepLabel).font(.llLabelBold).foregroundStyle(Theme.Palette.muted)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(state.stepLabel)
        .accessibilityIdentifier("learn.lesson.step")
    }

    // MARK: Pages

    @ViewBuilder
    private var page: some View {
        switch state.step {
        case let .card(index):
            if state.cards.indices.contains(index) { cardPage(state.cards[index]) }
        case .fact:
            factPage
        case let .question(index):
            if state.questions.indices.contains(index) { questionPage(state.questions[index]) }
        case .result:
            if let result = state.result { LearnResultView(result: result, questions: state.questions, actions: actions) }
        }
    }

    private func cardPage(_ card: LearnLessonViewState.Card) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            InkCard(shape: .hero, hero: true, padding: Theme.Spacing.l) {
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Image(systemName: state.symbol)
                        .font(.system(size: 26, weight: .semibold))
                        .frame(width: 48, height: 48)
                        .inkSurface(.badge, fill: Theme.Palette.money)
                        .foregroundStyle(Theme.Palette.onArea)
                        .accessibilityHidden(true)
                    Text(card.title).font(.llTitle).fixedSize(horizontal: false, vertical: true)
                        .accessibilityAddTraits(.isHeader)
                    Text(card.text).font(.llBody).fixedSize(horizontal: false, vertical: true)
                }
            }
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("learn.lesson.card.\(card.id)")
            askPenny
        }
    }

    private var factPage: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            ForEach(state.facts) { fact in
                InkCard(shape: .cardAlt, hero: fact.id == 0, padding: Theme.Spacing.l) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        Text(L10n.tr("The real number")).llEyebrow().foregroundStyle(Theme.Palette.muted)
                        if let number = fact.number {
                            Text(number)
                                .font(.llHero)
                                .lineLimit(1)
                                .minimumScaleFactor(0.5)
                                .accessibilityIdentifier("learn.lesson.factNumber")
                        }
                        Text(fact.text).font(.llBody).fixedSize(horizontal: false, vertical: true)
                        if let why = fact.whyText {
                            Text(why)
                                .font(.llBodyBold)
                                .fixedSize(horizontal: false, vertical: true)
                                .accessibilityIdentifier("learn.lesson.why.\(fact.id)")
                        }
                        VStack(alignment: .leading, spacing: 2) {
                            Text(fact.sourceLabel).font(.llLabelBold)
                            Text(fact.checkedText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                        if let url = fact.sourceURL {
                            Link(destination: url) {
                                HStack(spacing: 6) {
                                    Text(L10n.tr("Open the source"))
                                    Image(systemName: "arrow.up.right").font(.system(size: 13, weight: .bold))
                                }
                            }
                            .buttonStyle(.text)
                            .accessibilityLabel(L10n.tr("Open the source: \(fact.sourceLabel)"))
                            .accessibilityHint(L10n.tr("Opens the website in Safari"))
                            .accessibilityIdentifier("learn.lesson.source.\(fact.id)")
                        }
                    }
                }
            }
            askPenny
        }
    }

    private func questionPage(_ question: LearnLessonViewState.Question) -> some View {
        InkCard(shape: .cardAlt, padding: Theme.Spacing.l) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text(question.text).font(.llBodyBold).fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)
                ForEach(question.choices) { choice in
                    let selected = question.selectedChoiceID == choice.id
                    Button { actions.onChoose(question.id, choice.id) } label: {
                        HStack(spacing: Theme.Spacing.s) {
                            Text(choice.text).fixedSize(horizontal: false, vertical: true)
                            Spacer(minLength: 0)
                            if selected { LLIconImage(.check, size: 24) }
                        }
                    }
                    .buttonStyle(LearnChoiceStyle(selected: selected))
                    .disabled(state.isSubmitting)
                    .accessibilityAddTraits(selected ? .isSelected : [])
                    .accessibilityIdentifier("learn.lesson.choice.\(question.id).\(choice.id)")
                }
            }
        }
    }

    private var askPenny: some View {
        Button(action: actions.onAskPenny) {
            HStack(spacing: Theme.Spacing.s) {
                PennyView(mood: .smiling, size: 28)
                Text(L10n.tr("Ask Penny about this lesson"))
            }
        }
        .buttonStyle(.text)
        .accessibilityLabel(L10n.tr("Ask Penny about this lesson"))
        .accessibilityIdentifier("learn.lesson.askPenny")
    }

    // MARK: Bottom bar

    @ViewBuilder
    private var bottomBar: some View {
        if state.step != .result {
            HStack(spacing: Theme.Spacing.m) {
                if state.stepIndex > 0 {
                    Button(action: actions.onBack) {
                        Chevron(direction: .left)
                    }
                    .buttonStyle(.second)
                    .frame(width: 72)
                    .accessibilityLabel(L10n.tr("Back"))
                    .accessibilityIdentifier("learn.lesson.back")
                }
                primaryButton
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.vertical, Theme.Spacing.m)
            .background(Theme.Palette.paper.ignoresSafeArea(edges: .bottom))
        }
    }

    @ViewBuilder
    private var primaryButton: some View {
        let isLast = state.stepIndex == state.steps.count - 1
        if let question = state.currentQuestion {
            if isLast {
                Button(action: actions.onSubmit) {
                    Text(state.isSubmitting ? L10n.tr("Checking...") : L10n.tr("Check answers")).lineLimit(1).minimumScaleFactor(0.7)
                }
                .buttonStyle(.main)
                .disabled(!state.questions.allSatisfy { $0.selectedChoiceID != nil } || state.isSubmitting)
                .accessibilityIdentifier("learn.lesson.submit")
            } else {
                Button(action: actions.onNext) {
                    Text(L10n.tr("Next question")).lineLimit(1).minimumScaleFactor(0.7)
                }
                .buttonStyle(.main)
                .disabled(question.selectedChoiceID == nil)
                .accessibilityIdentifier("learn.lesson.next")
            }
        } else {
            let startsQuiz = state.steps.indices.contains(state.stepIndex + 1) && { if case .question = state.steps[state.stepIndex + 1] { true } else { false } }()
            Button(action: actions.onNext) {
                Text(startsQuiz ? L10n.tr("Start the quiz") : L10n.tr("Next")).lineLimit(1).minimumScaleFactor(0.7)
            }
            .buttonStyle(.main)
            .accessibilityIdentifier("learn.lesson.next")
        }
    }
}

/// Pass: Penny cheers, "Next lesson". Fail: "Try again". Both list every question with its explanation.
struct LearnResultView: View {
    let result: LearnLessonViewState.Result
    let questions: [LearnLessonViewState.Question]
    let actions: LearnLessonActions
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var cheer = false

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            InkCard(shape: .hero, fill: result.passed ? Theme.Palette.money : Theme.Palette.surface, hero: true, padding: Theme.Spacing.xl) {
                HStack(spacing: Theme.Spacing.l) {
                    PennyView(mood: result.passed ? .happy : .thinking, size: 72)
                        .scaleEffect(cheer ? 1.12 : 1)
                        .rotationEffect(.degrees(cheer ? -8 : 0))
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        Text(result.headline).font(.llTitle).fixedSize(horizontal: false, vertical: true)
                        Text(result.scoreText).font(.llBodyBold)
                        Text(result.detail).font(.llLabel).fixedSize(horizontal: false, vertical: true)
                    }
                    .foregroundStyle(result.passed ? Theme.Palette.onArea : Theme.Palette.ink)
                }
            }
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier(result.passed ? "learn.result.passed" : "learn.result.failed")
            .sensoryFeedback(result.passed ? .success : .warning, trigger: result.passed)
            .onAppear {
                guard result.passed, !reduceMotion else { return }
                withAnimation(.spring(response: 0.35, dampingFraction: 0.45)) { cheer = true }
                Task { @MainActor in
                    try? await Task.sleep(for: .milliseconds(450))
                    withAnimation(Motion.standard) { cheer = false }
                }
            }
            VStack(spacing: Theme.Spacing.s) {
                if result.passed {
                    if let next = result.nextLessonID {
                        Button { actions.onNextLesson(next) } label: {
                            Text(L10n.tr("Next lesson")).lineLimit(1).minimumScaleFactor(0.7)
                        }
                        .buttonStyle(.main)
                        .accessibilityHint(result.nextText ?? "")
                        .accessibilityIdentifier("learn.result.nextLesson")
                    }
                } else {
                    Button(action: actions.onTryAgain) {
                        Text(L10n.tr("Try again")).lineLimit(1).minimumScaleFactor(0.7)
                    }
                    .buttonStyle(.main)
                    .accessibilityIdentifier("learn.result.tryAgain")
                }
                Button(action: actions.onClose) {
                    Text(L10n.tr("Back to the path")).lineLimit(1).minimumScaleFactor(0.7)
                }
                .buttonStyle(.second)
                .accessibilityIdentifier("learn.result.backToPath")
            }
            Text(L10n.tr("Your answers")).llEyebrow().foregroundStyle(Theme.Palette.muted)
                .accessibilityAddTraits(.isHeader)
            ForEach(questions) { question in
                LearnAnswerReview(question: question)
            }
            Button(action: actions.onAskPenny) {
                HStack(spacing: Theme.Spacing.s) {
                    PennyView(mood: .smiling, size: 28)
                    Text(L10n.tr("Ask Penny about this lesson"))
                }
            }
            .buttonStyle(.text)
            .accessibilityLabel(L10n.tr("Ask Penny about this lesson"))
            .accessibilityIdentifier("learn.result.askPenny")
        }
    }
}

/// One graded question: right or wrong, the right answer, and why.
struct LearnAnswerReview: View {
    let question: LearnLessonViewState.Question

    private var chosen: String? { question.choices.first { $0.id == question.selectedChoiceID }?.text }
    private var right: String? { question.choices.first { $0.id == question.correctChoiceID }?.text }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            Image(systemName: question.isCorrect == true ? "checkmark" : "xmark")
                .font(.system(size: 16, weight: .heavy))
                .foregroundStyle(Theme.Palette.onArea)
                .frame(width: 32, height: 32)
                .background(Circle().fill(question.isCorrect == true ? Theme.Palette.money : Theme.Palette.health))
                .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: Theme.chipOutline))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                Text(question.text).font(.llBodyBold).fixedSize(horizontal: false, vertical: true)
                if question.isCorrect != true, let chosen {
                    Text(L10n.tr("Your answer: \(chosen)")).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                if let right {
                    Text(L10n.tr("Right answer: \(right)")).font(.llLabelBold)
                }
                if let why = question.explanation {
                    Text(why).font(.llBody).fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("learn.result.explanation.\(question.id)")
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(Theme.Spacing.l)
        .inkSurface(.card, lineWidth: Theme.chipOutline)
        .accessibilityElement(children: .combine)
        .accessibilityLabel((question.isCorrect == true ? L10n.tr("Right") : L10n.tr("Wrong")) + ". " + question.text)
    }
}

/// Quiz choice: 44 pt minimum, 2 pt outline, ink fill when picked.
private struct LearnChoiceStyle: ButtonStyle {
    let selected: Bool

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.llBodyBold)
            .foregroundStyle(selected ? Theme.Palette.onArea : Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.m)
            .padding(.vertical, Theme.Spacing.s)
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .inkSurface(.buttonThird, fill: selected ? Theme.Palette.home : Theme.Palette.surface, lineWidth: Theme.chipOutline)
            .offset(x: configuration.isPressed ? 2 : 0, y: configuration.isPressed ? 2 : 0)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Card · light") { LearnLessonView(state: LearnFixtures.lessonCard) }
#Preview("Card · dark") { LearnLessonView(state: LearnFixtures.lessonCard).previewDark() }
#Preview("Card · AX3") { LearnLessonView(state: LearnFixtures.lessonCard).previewLargeType() }
#Preview("Fact · light") { LearnLessonView(state: LearnFixtures.lessonFact) }
#Preview("Fact · dark") { LearnLessonView(state: LearnFixtures.lessonFact).previewDark() }
#Preview("Fact · AX3") { LearnLessonView(state: LearnFixtures.lessonFact).previewLargeType() }
#Preview("Question · light") { LearnLessonView(state: LearnFixtures.lessonQuestion) }
#Preview("Question · dark") { LearnLessonView(state: LearnFixtures.lessonQuestion).previewDark() }
#Preview("Question · AX3") { LearnLessonView(state: LearnFixtures.lessonQuestion).previewLargeType() }
#Preview("Pass · light") { LearnLessonView(state: LearnFixtures.resultPass) }
#Preview("Pass · dark") { LearnLessonView(state: LearnFixtures.resultPass).previewDark() }
#Preview("Pass · AX3") { LearnLessonView(state: LearnFixtures.resultPass).previewLargeType() }
#Preview("Fail · light") { LearnLessonView(state: LearnFixtures.resultFail) }
#Preview("Fail · dark") { LearnLessonView(state: LearnFixtures.resultFail).previewDark() }
#Preview("Fail · AX3") { LearnLessonView(state: LearnFixtures.resultFail).previewLargeType() }
#Preview("Locked · light") { LearnLessonView(state: LearnFixtures.lessonLocked) }
#Preview("Loading · light") { LearnLessonView(state: LearnFixtures.lessonLoading) }
