// Draft by W9. "Type a code instead" from the Play tab Join button (ADR 0052).
import SwiftUI

/// Small screen: type a 6-character room code and join.
struct RoomCodeEntryView: View {
    let state: RoomEntryViewState
    var actions: RoomEntryActions = .noop
    var onClose: () -> Void = {}
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            ScreenHeader(title: "Join a game", leading: HeaderSquareButton(kind: .close, identifier: "codeEntry.close", action: onClose))
            Text("Type the 6-character code from the host's screen.")
                .font(.llBody)
                .fixedSize(horizontal: false, vertical: true)
            TextField("Room code", text: Binding(get: { state.joinCode }, set: actions.onJoinCodeChange))
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
                .focused($focused)
                .font(.llHero)
                .multilineTextAlignment(.center)
                .padding(.horizontal, Theme.Spacing.m)
                .frame(minHeight: 72)
                .inkSurface(.hero, hero: true)
                .accessibilityIdentifier("codeEntry.code")
            if let error = state.errorText {
                Chip(text: error, fill: Theme.Palette.health)
                    .accessibilityIdentifier("codeEntry.error")
            }
            Button(state.busyText ?? "Join", action: actions.onJoin)
                .buttonStyle(.main)
                .disabled(!state.canJoin)
                .accessibilityIdentifier("codeEntry.join")
            Spacer(minLength: 0)
        }
        .foregroundStyle(Theme.Palette.ink)
        .padding(.horizontal, Theme.Spacing.margin)
        .padding(.top, Theme.Spacing.m)
        .paperBackground()
        .onAppear { focused = true }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Code · light") { RoomCodeEntryView(state: RoomFlowFixtures.entry(joinCode: "K7Q2ZP")) }
#Preview("Code · dark") { RoomCodeEntryView(state: RoomFlowFixtures.entry(joinCode: "K7Q")).previewDark() }
#Preview("Code · AX3") { RoomCodeEntryView(state: RoomFlowFixtures.entryError).previewLargeType() }
