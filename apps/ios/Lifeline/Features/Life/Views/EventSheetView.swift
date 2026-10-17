import SwiftUI

/// One real-data event with its choices. The player must pick one to continue.
struct EventSheetView: View {
    let state: EventSheetViewState
    var actions: EventSheetActions = .noop
    @Namespace private var glassNamespace

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                HStack(alignment: .top, spacing: Theme.Spacing.m) {
                    Text(state.emoji)
                        .font(.system(size: 48))
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        Text("\(String(state.year)) · Age \(state.age)")
                            .font(.subheadline.monospacedDigit())
                            .foregroundStyle(.secondary)
                        Text(state.title)
                            .font(.title2.bold())
                            .accessibilityAddTraits(.isHeader)
                            .accessibilityIdentifier("event.title")
                    }
                }

                Text(state.text)
                    .font(.body)
                    .fixedSize(horizontal: false, vertical: true)

                if state.isAIText {
                    Label("Words written by AI. Numbers come from the game engine.", systemImage: "sparkles")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }

                GlassEffectContainer(spacing: Theme.Spacing.m) {
                    VStack(spacing: Theme.Spacing.m) {
                        ForEach(state.choices) { choice in
                            ChoiceButton(choice: choice, disabled: state.isSubmitting) {
                                actions.onChoose(choice.id)
                            }
                            .glassEffectID(choice.id, in: glassNamespace)
                        }
                    }
                }

                if !state.sources.isEmpty {
                    SourcesFooter(sources: state.sources)
                }
            }
            .padding(Theme.Spacing.xl)
        }
        .accessibilityIdentifier("event.sheet")
    }
}

/// A choice as a large glass button with an optional cost hint.
struct ChoiceButton: View {
    let choice: EventSheetViewState.Choice
    let disabled: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.m) {
                if let emoji = choice.emoji {
                    Text(emoji).font(.title2).accessibilityHidden(true)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(choice.label).font(.headline)
                    if let hint = choice.hint {
                        Text(hint)
                            .font(.subheadline.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }
                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .padding(.vertical, Theme.Spacing.xs)
            .contentShape(.rect)
        }
        .buttonStyle(.glass)
        .disabled(disabled)
        .accessibilityLabel([choice.label, choice.hint].compactMap { $0 }.joined(separator: ". "))
        .accessibilityIdentifier("event.choice.\(choice.id)")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Rent rise · light") {
    EventSheetView(state: Fixtures.Event.rentRise)
}

#Preview("Rent rise · dark") {
    EventSheetView(state: Fixtures.Event.rentRise).previewDark()
}

#Preview("Rent rise · AX3") {
    EventSheetView(state: Fixtures.Event.rentRise).previewLargeType()
}

#Preview("Crisis · light") {
    EventSheetView(state: Fixtures.Event.crisis)
}

#Preview("Crisis · dark") {
    EventSheetView(state: Fixtures.Event.crisis).previewDark()
}

#Preview("Crisis · AX3") {
    EventSheetView(state: Fixtures.Event.crisis).previewLargeType()
}

#Preview("Submitting · light") {
    EventSheetView(state: Fixtures.Event.submitting)
}

#Preview("Submitting · dark") {
    EventSheetView(state: Fixtures.Event.submitting).previewDark()
}

#Preview("Submitting · AX3") {
    EventSheetView(state: Fixtures.Event.submitting).previewLargeType()
}
