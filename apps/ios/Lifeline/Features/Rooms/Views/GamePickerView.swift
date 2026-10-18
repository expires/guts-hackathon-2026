// Draft by W9. Host's one small sheet: pick the game and its options (ADR 0059).
import SwiftUI

/// Money Quiz, Same Decision or Same Life, with only that game's options below.
struct GamePickerView: View {
    let state: GamePickerViewState
    var actions: GamePickerActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: L10n.tr("Pick a game"), leading: HeaderSquareButton(kind: .close, identifier: "picker.close", action: actions.onClose))
                VStack(spacing: Theme.Spacing.s) {
                    ForEach(state.games) { game in
                        gameRow(game)
                    }
                }
                options
                Button(state.confirmTitle, action: actions.onConfirm)
                    .buttonStyle(.main)
                    .disabled(!state.canConfirm)
                    .accessibilityIdentifier("picker.confirm")
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
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
            }
            .foregroundStyle(isOn ? Theme.Palette.surface : Theme.Palette.ink)
            .padding(Theme.Spacing.m)
            .frame(minHeight: Theme.minTarget)
            .inkSurface(.card, fill: isOn ? Theme.Palette.ink : Theme.Palette.surface)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isOn ? [.isSelected, .isButton] : .isButton)
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
        default:
            LLToggleRow(title: L10n.tr("Quick Life"), subtitle: L10n.tr("Ages 18 to 25 in about 2 minutes"), isOn: state.quick, identifier: "picker.quick", onChange: actions.onQuick)
            switch state.pathsPhase {
            case .loading:
                HStack(spacing: Theme.Spacing.s) {
                    ForEach(0..<3, id: \.self) { _ in LLSkeleton(.block(height: Theme.minTarget)) }
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Loading paths")
            case let .failed(error):
                ErrorStateView(state: error)
            case .ready where !state.students.isEmpty:
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Text("Everyone plays").font(.llLabelBold)
                    ForEach(state.students) { student in
                        studentCard(student)
                    }
                }
            case .ready:
                LLChoiceChips(title: L10n.tr("Start path"), options: state.paths.map { .init(id: $0.id, label: $0.label) }, selection: state.pathID ?? "", identifier: "picker.path", onSelect: actions.onPath)
                if let path = state.paths.first(where: { $0.id == state.pathID }) {
                    Text(path.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
            }
            yearStepper
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

#Preview("Quiz · light") { GamePickerView(state: RoomFlowFixtures.pickerQuiz) }
#Preview("Quiz · dark") { GamePickerView(state: RoomFlowFixtures.pickerQuiz).previewDark() }
#Preview("Quiz · AX3") { GamePickerView(state: RoomFlowFixtures.pickerQuiz).previewLargeType() }
#Preview("Same Life · light") { GamePickerView(state: RoomFlowFixtures.pickerSameLife) }
#Preview("Same Decision · dark") { GamePickerView(state: RoomFlowFixtures.pickerDecision).previewDark() }
