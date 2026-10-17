import SwiftUI

/// "Why?" bottom sheet (handoff Money-Why): Penny with the 3 evidence points as speech bubbles,
/// a rate chart from the evidence facts, the confidence reason, the lesson and two buttons.
struct NextMoveWhyView: View {
    let state: NextMoveWhyViewState
    var actions: NextMoveWhyActions = .noop
    /// "Test it in Life". Nil hides the button (move not testable).
    var onTestIt: (() -> Void)?

    private let bubbleShapes: [HandCut] = [HandCut((4, 18, 16, 18)), HandCut((18, 16, 18, 14)), HandCut((16, 18, 14, 18))]

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                    ScreenHeader(title: "Why \(state.action.prefix(1).lowercased() + state.action.dropFirst())?") {
                        HeaderSquareButton(kind: .close, identifier: "why.close", action: actions.onClose)
                    }
                    if state.isSampleData { DemoDataBadge() }
                    Text(state.headline).font(.llBodyBold)
                    HStack(alignment: .top, spacing: 10) {
                        PennyView(mood: PennyView.mood(confidence: state.confidence), size: 44)
                        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                            ForEach(state.evidence) { point in
                                Text(point.text).font(.llBody).fixedSize(horizontal: false, vertical: true)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 10)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .inkSurface(bubbleShapes[point.id % bubbleShapes.count])
                                .accessibilityElement(children: .combine)
                                .accessibilityIdentifier("why.evidence.\(point.id)")
                            }
                        }
                    }
                    if !state.rates.isEmpty {
                        rateChart
                    } else if let sources = state.ratesSourceText {
                        Text("Sources: \(sources)").font(.llLabel).foregroundStyle(Theme.Palette.muted).accessibilityIdentifier("why.sources")
                    }
                    HStack(alignment: .top, spacing: 10) {
                        Chip(text: state.confidenceChip)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(state.confidenceLabel).font(.llLabel)
                            Text(state.worstCaseText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.xs)
                    lesson
                    if AppFeatures.game && state.hasDecisionDetail {
                        Button("See the full decision", action: actions.onOpenDecision)
                            .buttonStyle(.text)
                            .accessibilityIdentifier("why.decision")
                    }
                }
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.top, Theme.Spacing.l)
            }
            HStack(spacing: Theme.Spacing.s) {
                if AppFeatures.game, let onTestIt {
                    Button("Test it in Life", action: onTestIt)
                        .buttonStyle(.main)
                        .accessibilityIdentifier("why.testIt")
                }
                Button("Got it", action: actions.onClose)
                    .buttonStyle(.second)
                    .accessibilityIdentifier("why.gotIt")
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.vertical, Theme.Spacing.m)
        }
    }

    private var rateChart: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(state.rates) { rate in
                HStack(spacing: 10) {
                    Text(rate.label)
                        .font(rate.isHighlighted ? .llLabelBold : .llLabel)
                        .frame(width: 92, alignment: .leading)
                    GeometryReader { proxy in
                        let shape = HandCut((6, 9, 5, 8))
                        Group {
                            if rate.isReference {
                                shape.stroke(Theme.Palette.muted, style: StrokeStyle(lineWidth: 3, dash: [6, 4]))
                            } else {
                                shape.fill(rate.isHighlighted ? Theme.Palette.ink : Theme.Palette.surface)
                                    .overlay(shape.strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline))
                            }
                        }
                        .frame(width: max(12, proxy.size.width * rate.fraction))
                    }
                    .frame(height: 16)
                    Text(rate.valueText).font(.llLabelBold).frame(width: 52, alignment: .trailing)
                }
                .foregroundStyle(rate.isReference ? Theme.Palette.muted : Theme.Palette.ink)
                .accessibilityElement(children: .combine)
            }
            if let sources = state.ratesSourceText {
                Text("Sources: \(sources)").font(.llLabel).foregroundStyle(Theme.Palette.muted).accessibilityIdentifier("why.sources")
            }
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, 14)
        .inkSurface(.card)
        .accessibilityIdentifier("why.rates")
    }

    @ViewBuilder
    private var lesson: some View {
        switch state.lessonPhase {
        case let .loading(loading):
            LoadingStateView(state: loading)
        case let .failed(error):
            ErrorStateView(state: error, onRetry: actions.onRetry)
        case .ready:
            if let lesson = state.lesson {
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Label(lesson.title, icon: .lesson, size: 32).font(.llBodyBold)
                    ForEach(lesson.sentences, id: \.self) { Text($0).font(.llBody) }
                    if let personal = lesson.personal {
                        Text(personal).font(.llBodyBold).accessibilityIdentifier("why.personal")
                    }
                    if AppFeatures.game {
                        Button("Open the lesson", action: actions.onOpenLesson)
                            .buttonStyle(.text)
                            .accessibilityIdentifier("why.openLesson")
                    }
                }
                .padding(Theme.Spacing.l)
                .frame(maxWidth: .infinity, alignment: .leading)
                .inkSurface(.cardAlt)
            } else {
                Text("No lesson for this move yet.").font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Mortgage · light") { LLSheetFrame { NextMoveWhyView(state: Fixtures.Why.mortgage, onTestIt: {}) } }
#Preview("Mortgage · dark") { LLSheetFrame { NextMoveWhyView(state: Fixtures.Why.mortgage, onTestIt: {}) }.previewDark() }
#Preview("Mortgage · AX3") { LLSheetFrame { NextMoveWhyView(state: Fixtures.Why.mortgage, onTestIt: {}) }.previewLargeType() }
#Preview("No lesson · light") { LLSheetFrame { NextMoveWhyView(state: Fixtures.Why.noLesson) } }
#Preview("With lesson · light") { LLSheetFrame { NextMoveWhyView(state: Fixtures.Why.withLesson) } }
#Preview("Loading lesson · light") { LLSheetFrame { NextMoveWhyView(state: Fixtures.Why.loadingLesson) } }
#Preview("Lesson error · dark") { LLSheetFrame { NextMoveWhyView(state: Fixtures.Why.lessonError) }.previewDark() }
