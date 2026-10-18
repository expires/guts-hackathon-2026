// Draft by W9. Host's one small sheet: pick the game and its options (ADR 0059, PENNY_V3_BUILD.md F5).
import SwiftUI

/// Quick Life first, then Money Quiz (cut games only with `FeatureFlags.showsCutFeatures`).
/// Quick Life opens the student step: one tap on a student picks the game. Money Quiz shows its options below.
struct GamePickerView: View {
    let state: GamePickerViewState
    var actions: GamePickerActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                switch state.step {
                case .games: gamesStep
                case .students: studentsStep
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    @ViewBuilder
    private var gamesStep: some View {
        ScreenHeader(title: L10n.tr("Pick a game"), leading: HeaderSquareButton(kind: .close, identifier: "picker.close", action: actions.onClose))
        VStack(spacing: Theme.Spacing.s) {
            ForEach(state.games) { game in
                gameRow(game)
            }
        }
        if state.showsConfirm {
            options
            confirmButton
        }
    }

    /// Quick Life: the premade students. The year is preset, so there is no year step.
    @ViewBuilder
    private var studentsStep: some View {
        ScreenHeader(title: L10n.tr("Pick a student"), leading: HeaderSquareButton(kind: .back, identifier: "picker.back", action: actions.onBack))
        Text("Everyone plays this student from 18 to 25. Tap one to pick it.")
            .font(.llBody)
            .foregroundStyle(Theme.Palette.muted)
            .fixedSize(horizontal: false, vertical: true)
        switch state.pathsPhase {
        case .loading:
            VStack(spacing: Theme.Spacing.s) {
                ForEach(0..<5, id: \.self) { _ in LLSkeleton(.block(height: 72)) }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(L10n.tr("Loading paths"))
        case let .failed(error):
            ErrorStateView(state: error)
        case .ready where !state.students.isEmpty:
            VStack(spacing: Theme.Spacing.s) {
                ForEach(state.students) { student in
                    studentCard(student)
                }
            }
        case .ready:
            // Older server without premade students: pick a Quick Life path, then confirm.
            LLChoiceChips(title: L10n.tr("Start path"), options: state.paths.map { .init(id: $0.id, label: $0.label) }, selection: state.pathID ?? "", identifier: "picker.path", onSelect: actions.onPath)
            confirmButton
        }
    }

    private var confirmButton: some View {
        Button(state.confirmTitle, action: actions.onConfirm)
            .buttonStyle(.main)
            .disabled(!state.canConfirm)
            .accessibilityIdentifier("picker.confirm")
    }

    private func gameRow(_ game: GamePickerViewState.Option) -> some View {
        let isOn = game.id == state.selectedGame
        return Button { actions.onSelectGame(game.id) } label: {
            HStack(spacing: Theme.Spacing.m) {
                LLIconImage(LLIcon(rawValue: game.icon) ?? .lesson, size: 32)
                VStack(alignment: .leading, spacing: 2) {
                    Text(game.label).font(.llBodyBold)
                    Text(game.detail).font(.llLabel).fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if game.id == GamePickerViewState.quickLifeID {
                    Image(systemName: "chevron.right").font(.llBodyBold).accessibilityHidden(true)
                }
            }
            .foregroundStyle(isOn ? Theme.Palette.surface : Theme.Palette.ink)
            .padding(Theme.Spacing.m)
            .frame(minHeight: Theme.minTarget)
            .inkSurface(.card, fill: isOn ? Theme.Palette.ink : Theme.Palette.surface)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isOn ? [.isSelected, .isButton] : .isButton)
        .accessibilityHint(game.id == GamePickerViewState.quickLifeID ? L10n.tr("Opens the students") : "")
        .accessibilityIdentifier("picker.game.\(game.id)")
    }

    @ViewBuilder
    private var options: some View {
        switch state.selectedGame {
        case RoomGameKind.quiz.rawValue:
            LLStepper(
                title: L10n.tr("Questions"),
                valueText: "\(state.questions)",
                canDecrement: state.questions > 3,
                canIncrement: state.questions < 15,
                identifier: "picker.questions",
                onDecrement: { actions.onQuestions(state.questions - 1) },
                onIncrement: { actions.onQuestions(state.questions + 1) }
            )
            LLChoiceChips(title: L10n.tr("Topic"), options: state.topics.map { .init(id: $0.id, label: $0.label) }, selection: state.topic, identifier: "picker.topic", onSelect: actions.onTopic)
        case RoomGameKind.sameDecision.rawValue:
            yearStepper
        case RoomGameKind.sameLife.rawValue:
            // Full life (cut): a path and a year.
            LLChoiceChips(title: L10n.tr("Start path"), options: state.paths.map { .init(id: $0.id, label: $0.label) }, selection: state.pathID ?? "", identifier: "picker.path", onSelect: actions.onPath)
            yearStepper
        default:
            EmptyView()
        }
    }

    private func studentCard(_ student: GamePickerViewState.Option) -> some View {
        let isOn = student.id == state.studentID
        return Button { actions.onStudent(student.id) } label: {
            HStack(spacing: Theme.Spacing.m) {
                LLIconImage(LLIcon(rawValue: student.icon) ?? .facePriya, size: 32)
                VStack(alignment: .leading, spacing: 2) {
                    Text(student.label).font(.llBodyBold)
                    Text(student.detail).font(.llLabel).fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if isOn { LLIconImage(.check, size: 24) }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(Theme.Spacing.m)
            .frame(minHeight: Theme.minTarget)
            .inkSurface(.card, fill: isOn ? Theme.Palette.money : Theme.Palette.surface, lineWidth: isOn ? Theme.outline : Theme.chipOutline)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isOn ? [.isSelected, .isButton] : .isButton)
        .accessibilityHint(L10n.tr("Picks Quick Life with this student"))
        .accessibilityIdentifier("picker.student.\(student.id)")
    }

    private var yearStepper: some View {
        LLStepper(
            title: L10n.tr("Year in history"),
            valueText: String(state.startYear),
            canDecrement: state.startYear > state.minYear,
            canIncrement: state.startYear < state.maxYear,
            identifier: "picker.year",
            onDecrement: { actions.onYear(state.startYear - 1) },
            onIncrement: { actions.onYear(state.startYear + 1) }
        )
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Games · light") { GamePickerView(state: RoomFlowFixtures.pickerGames) }
#Preview("Games · dark") { GamePickerView(state: RoomFlowFixtures.pickerGames).previewDark() }
#Preview("Games · AX3") { GamePickerView(state: RoomFlowFixtures.pickerGames).previewLargeType() }
#Preview("Students · light") { GamePickerView(state: RoomFlowFixtures.pickerStudents) }
#Preview("Students · dark") { GamePickerView(state: RoomFlowFixtures.pickerStudents).previewDark() }
#Preview("Students · AX3") { GamePickerView(state: RoomFlowFixtures.pickerStudents).previewLargeType() }
#Preview("Quiz · light") { GamePickerView(state: RoomFlowFixtures.pickerQuiz) }
#Preview("Quiz · dark") { GamePickerView(state: RoomFlowFixtures.pickerQuiz).previewDark() }
#Preview("Quiz · AX3") { GamePickerView(state: RoomFlowFixtures.pickerQuiz).previewLargeType() }
