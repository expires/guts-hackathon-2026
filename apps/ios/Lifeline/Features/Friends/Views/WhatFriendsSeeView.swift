import SwiftUI

/// Your own card exactly as friends see it, plus the two things you can change.
struct WhatFriendsSeeView: View {
    let state: MyCardState
    var actions: FriendsActions = .noop
    var onClose: () -> Void = {}

    var body: some View {
        SheetContainer(title: "What friends see", closeIdentifier: "whatSee.close", onClose: onClose) {
            Text("This is your card, exactly as your friends see it.")
                .font(.llBody)
                .foregroundStyle(Theme.Palette.muted)
            if let preview = state.preview {
                FriendCardContent(detail: preview)
            }
            settings
        }
        .background(Theme.Palette.paper)
    }

    private var settings: some View {
        InkCard(shape: .cardAlt) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text("Your settings").font(.llBodyBold).accessibilityAddTraits(.isHeader)
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    Text("Name your friends see").font(.llLabelBold)
                    TextField("Your name", text: Binding(get: { state.nameDraft }, set: actions.onNameChange))
                        .font(.llBody)
                        .textInputAutocapitalization(.words)
                        .submitLabel(.done)
                        .onSubmit { if state.canSaveName { actions.onSaveName() } }
                        .padding(.horizontal, Theme.Spacing.m)
                        .frame(minHeight: Theme.buttonHeight)
                        .inkSurface(.buttonAlt)
                        .accessibilityLabel("Name your friends see")
                        .accessibilityIdentifier("whatSee.name")
                }
                Button("Save name", icon: .check) { actions.onSaveName() }
                    .buttonStyle(.second)
                    .disabled(!state.canSaveName)
                    .accessibilityIdentifier("whatSee.saveName")
                RuleDivider()
                LLToggleRow(
                    title: "Share my investment mix",
                    subtitle: "Shows percentages like 80% shares. Never amounts.",
                    isOn: state.shareMix,
                    identifier: "whatSee.shareMix",
                    onChange: actions.onShareMix
                )
                .disabled(state.isSaving)
                if let error = state.errorText {
                    Label(error, icon: .why).font(.llLabelBold)
                        .accessibilityIdentifier("whatSee.error")
                }
                Label("Amounts are never shared. Friends only see scores and percentages.", icon: .lock)
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("whatSee.note")
            }
        }
    }
}

// MARK: - Previews

#Preview("What friends see · light") { LLSheetFrame { WhatFriendsSeeView(state: Fixtures.Friends.mineHidden) } }
#Preview("What friends see, shared · light") { LLSheetFrame { WhatFriendsSeeView(state: Fixtures.Friends.mineShared) } }
#Preview("What friends see · dark") { LLSheetFrame { WhatFriendsSeeView(state: Fixtures.Friends.mineShared) }.previewDark() }
#Preview("What friends see · AX3") { LLSheetFrame { WhatFriendsSeeView(state: Fixtures.Friends.mineHidden) }.previewLargeType() }
