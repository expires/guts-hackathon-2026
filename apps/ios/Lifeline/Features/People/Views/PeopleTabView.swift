import SwiftUI

/// People tab (Relationships): family, partner, friends.
struct PeopleTabView: View {
    let state: PeopleTabViewState
    var actions: ActionTabActions = .noop

    var body: some View {
        SheetContainer(title: "People", closeIdentifier: "menu.close", onClose: actions.onClose) {
            RowGroup(title: L10n.tr("People close to me")) {
                if state.people.isEmpty {
                    ListRow(icon: .relationships, title: L10n.tr("No one close to you yet"), showsChevron: false)
                }
                ForEach(state.people) { person in
                    HStack(spacing: Theme.Spacing.m) {
                        LLIconImage(LLIcon.face(emoji: person.emoji), size: 32)
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            HStack {
                                Text(person.name).font(.llBodyBold)
                                Text(person.relation).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                Spacer()
                                Text("\(person.closeness)%").font(.llLabelBold)
                            }
                            InkProgressBar(value: Double(person.closeness) / 100, color: Theme.Palette.family, height: 14)
                        }
                    }
                    .padding(.vertical, Theme.Spacing.m)
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("\(person.name), \(person.relation), closeness \(person.closeness) out of 100")
                }
            }
            RowGroupTitle(text: L10n.tr("What you can do"))
            ActionList(actions: state.actions, isBusy: state.isBusy, onAction: actions.onAction, emptyText: L10n.tr("Nothing to do here this year."))
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Family · light") {
    PeopleTabView(state: Fixtures.Tabs.people).previewInNavigation()
}

#Preview("Family · dark") {
    PeopleTabView(state: Fixtures.Tabs.people).previewInNavigation().previewDark()
}

#Preview("Family · AX3") {
    PeopleTabView(state: Fixtures.Tabs.people).previewInNavigation().previewLargeType()
}
