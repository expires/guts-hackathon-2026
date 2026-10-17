import SwiftUI

/// People tab (Relationships): family, partner, friends.
struct PeopleTabView: View {
    let state: PeopleTabViewState
    var actions: ActionTabActions = .noop

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.l) {
                GlassCard {
                    VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                        if state.people.isEmpty {
                            Text("No one close to you yet.").foregroundStyle(.secondary)
                        }
                        ForEach(state.people) { person in
                            HStack(spacing: Theme.Spacing.m) {
                                Text(person.emoji).font(.title2).accessibilityHidden(true)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(person.name).font(.headline)
                                    Text(person.relation).font(.caption).foregroundStyle(.secondary)
                                    ProgressView(value: Double(person.closeness), total: 100)
                                        .tint(.pink)
                                }
                            }
                            .frame(minHeight: Theme.minTarget)
                            .accessibilityElement(children: .ignore)
                            .accessibilityLabel("\(person.name), \(person.relation), closeness \(person.closeness) out of 100")
                        }
                    }
                }
                if let outcome = state.outcome {
                    OutcomeBanner(outcome: outcome, onDismiss: actions.onDismissOutcome)
                }
                SectionTitle(text: "What to do")
                ActionList(actions: state.actions, isBusy: state.isBusy, onAction: actions.onAction)
            }
            .padding(Theme.Spacing.l)
        }
        .navigationTitle("People")
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
