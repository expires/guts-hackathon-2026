// Draft by W9. Circles in the Play tab (ADR 0052): habit ratios and improvement, never amounts.
import SwiftUI

/// Circles segment: your circles, a circle's members ranked by improvement, the weekly recap, create and join.
struct CirclesContent: View {
    let state: CirclesViewState
    var actions: CirclesActions = .noop

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            Text("Friends see habit scores only. Never your balance, pay or spending.")
                .font(.llLabel)
                .foregroundStyle(Theme.Palette.muted)
                .fixedSize(horizontal: false, vertical: true)
            if let error = state.errorText {
                Chip(text: error, fill: Theme.Palette.health).accessibilityIdentifier("circles.error")
            }
            if let busy = state.busyText {
                Text(busy).font(.llLabelBold).foregroundStyle(Theme.Palette.muted).accessibilityIdentifier("circles.busy")
            }
            switch state.phase {
            case .loading:
                SkeletonList(rows: 3, showsCard: true)
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                if let circle = state.circles.first(where: { $0.id == state.selectedID }) {
                    detail(circle)
                } else {
                    list
                    forms
                }
            }
        }
        .foregroundStyle(Theme.Palette.ink)
    }

    @ViewBuilder
    private var list: some View {
        if state.circles.isEmpty {
            Text("No circles yet. Make one for your flat or your course.").font(.llBody).foregroundStyle(Theme.Palette.muted)
        } else {
            VStack(spacing: 0) {
                ForEach(Array(state.circles.enumerated()), id: \.element.id) { offset, circle in
                    if offset > 0 { RuleDivider() }
                    Button { actions.onSelect(circle.id) } label: {
                        HStack(spacing: Theme.Spacing.m) {
                            LLIconImage(.family, size: 32)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(circle.name).font(.llBodyBold)
                                Text(L10n.tr("\(circle.detail) · code \(circle.code)")).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            Chevron()
                        }
                        .foregroundStyle(Theme.Palette.ink)
                        .padding(.horizontal, Theme.Spacing.l)
                        .padding(.vertical, Theme.Spacing.m)
                        .frame(minHeight: Theme.minTarget)
                        .contentShape(.rect)
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("circles.row.\(circle.id)")
                }
            }
            .inkSurface(.card)
        }
    }

    private var forms: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            BlockTitle(text: L10n.tr("Make a circle"))
            HStack(spacing: Theme.Spacing.s) {
                TextField("Circle name", text: Binding(get: { state.newName }, set: actions.onNameChange))
                    .font(.llBody)
                    .padding(.horizontal, Theme.Spacing.m)
                    .frame(minHeight: Theme.buttonHeight)
                    .inkSurface(.buttonThird)
                    .accessibilityIdentifier("circles.name")
                Button("Make", action: actions.onCreate)
                    .buttonStyle(.main)
                    .frame(width: 96)
                    .disabled(!state.canCreate)
                    .accessibilityIdentifier("circles.create")
            }
            BlockTitle(text: L10n.tr("Join a circle"))
            HStack(spacing: Theme.Spacing.s) {
                TextField("Circle code", text: Binding(get: { state.joinCode }, set: actions.onJoinCodeChange))
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                    .font(.llBody)
                    .padding(.horizontal, Theme.Spacing.m)
                    .frame(minHeight: Theme.buttonHeight)
                    .inkSurface(.buttonThird)
                    .accessibilityIdentifier("circles.code")
                Button("Join", action: actions.onJoin)
                    .buttonStyle(.main)
                    .frame(width: 96)
                    .disabled(!state.canJoin)
                    .accessibilityIdentifier("circles.join")
            }
        }
    }

    private func detail(_ circle: CirclesViewState.CircleRow) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            HStack(spacing: Theme.Spacing.m) {
                HeaderSquareButton(kind: .back, identifier: "circles.back") { actions.onSelect(nil) }
                VStack(alignment: .leading, spacing: 0) {
                    Text(circle.name).font(.llTitle)
                    Text(L10n.tr("\(circle.detail) · code \(circle.code)")).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            if let recap = circle.recap {
                HStack(alignment: .top, spacing: Theme.Spacing.m) {
                    LLIconImage(.pennySmiling, size: 40)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(circle.recapWeek.map { L10n.tr("Penny's recap · \($0)") } ?? L10n.tr("Penny's recap")).font(.llLabelBold)
                        Text(recap).font(.llBody).fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(Theme.Spacing.l)
                .inkSurface(.hero, hero: true)
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("circles.recap")
            }
            BlockTitle(text: L10n.tr("Most improved"))
            VStack(spacing: Theme.Spacing.m) {
                ForEach(circle.members) { member in
                    memberCard(member)
                }
            }
            Button("Leave this circle") { actions.onLeave(circle.id) }
                .buttonStyle(.text)
                .accessibilityIdentifier("circles.leave")
        }
    }

    private func memberCard(_ member: CirclesViewState.Member) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            HStack(spacing: Theme.Spacing.m) {
                Text(member.rank.map(String.init) ?? "-").font(.llBodyBold).frame(width: 20)
                LLIconImage(LLIcon(rawValue: member.face) ?? .faceTeen, size: 32)
                VStack(alignment: .leading, spacing: 0) {
                    Text(member.name).font(member.isYou ? .llBodyBold : .llBody)
                    Text(member.overall.map { L10n.tr("Habit score \($0) of 100") } ?? L10n.tr("No habit score yet")).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if !member.improvementText.isEmpty {
                    Chip(text: member.improvementText, fill: (member.improvement ?? 0) >= 0 ? Theme.Palette.money : Theme.Palette.health)
                }
            }
            ForEach(member.habits) { habit in
                HStack(spacing: Theme.Spacing.s) {
                    Text(habit.label).font(.llLabel).frame(width: 130, alignment: .leading)
                    InkProgressBar(value: Double(habit.value) / 100, color: Theme.Palette.work, height: 10)
                    Text("\(habit.value)").font(.llLabelBold).frame(width: 32, alignment: .trailing)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(L10n.tr("\(habit.label) \(habit.value) out of 100"))
            }
        }
        .padding(Theme.Spacing.m)
        .inkSurface(member.isYou ? .cardAlt : .card, fill: member.isYou ? Theme.Palette.paper : Theme.Palette.surface)
        .accessibilityIdentifier("circles.member.\(member.id)")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

private struct CirclesPreview: View {
    let state: CirclesViewState
    var body: some View {
        ScrollView { CirclesContent(state: state).padding(.horizontal, Theme.Spacing.margin) }.paperBackground()
    }
}

#Preview("List · light") { CirclesPreview(state: RoomFlowFixtures.circles) }
#Preview("List · dark") { CirclesPreview(state: RoomFlowFixtures.circles).previewDark() }
#Preview("Detail · light") { CirclesPreview(state: RoomFlowFixtures.circleDetail) }
#Preview("Detail · dark") { CirclesPreview(state: RoomFlowFixtures.circleDetail).previewDark() }
#Preview("Detail · AX3") { CirclesPreview(state: RoomFlowFixtures.circleDetail).previewLargeType() }
#Preview("Empty · light") { CirclesPreview(state: RoomFlowFixtures.circlesEmpty) }
