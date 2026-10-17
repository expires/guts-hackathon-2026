// Draft by W9. Room entry, lobby first (ADR 0052, 0059): open a lobby, or join by code or QR.
import SwiftUI

/// Open a lobby, or join one. Shown while the lobby opens, after an error, or from character select.
struct RoomEntryContent: View {
    let state: RoomEntryViewState
    var actions: RoomEntryActions = .noop

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            if let active = state.activeRoom { activeCard(active) }
            if let busy = state.busyText {
                Text(busy).font(.llLabelBold).foregroundStyle(Theme.Palette.muted)
                LobbySkeleton()
            }
            if let error = state.errorText {
                Text(error)
                    .font(.llBodyBold)
                    .foregroundStyle(Theme.Palette.onArea)
                    .padding(Theme.Spacing.m)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .inkSurface(.badge, fill: Theme.Palette.health, lineWidth: Theme.chipOutline)
                    .accessibilityIdentifier("roomEntry.error")
            }
            if state.activeRoom == nil {
                Button("Open a lobby", action: actions.onOpenLobby)
                    .buttonStyle(.main)
                    .disabled(!state.canOpenLobby)
                    .accessibilityIdentifier("room.openLobby")
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                BlockTitle(text: "Join a game")
                HStack(spacing: Theme.Spacing.s) {
                    TextField("Room code", text: Binding(get: { state.joinCode }, set: actions.onJoinCodeChange))
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()
                        .font(.llTitle)
                        .padding(.horizontal, Theme.Spacing.m)
                        .frame(minHeight: Theme.buttonHeight)
                        .inkSurface(.buttonThird)
                        .accessibilityIdentifier("room.code")
                    Button("Join", action: actions.onJoin)
                        .buttonStyle(.main)
                        .frame(width: 96)
                        .disabled(!state.canJoin)
                        .accessibilityIdentifier("room.join")
                }
                Button(action: actions.onScan) {
                    HStack(spacing: 10) {
                        LLIconImage(.scan, size: 24)
                        Text("Scan a QR code").lineLimit(1)
                    }
                }
                .buttonStyle(.second)
                .accessibilityIdentifier("room.scan")
            }
        }
        .foregroundStyle(Theme.Palette.ink)
        .disabled(state.busyText != nil)
    }

    private func activeCard(_ active: RoomEntryViewState.ActiveRoom) -> some View {
        Button(action: actions.onOpenActiveRoom) {
            HStack(spacing: Theme.Spacing.m) {
                VStack(alignment: .leading, spacing: 0) {
                    Text("Your room").llEyebrow()
                    Text(active.code).font(.llHero).lineLimit(1).minimumScaleFactor(0.6)
                    Text(active.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Chevron()
            }
            .padding(Theme.Spacing.l)
            .inkSurface(.hero, hero: true)
            .foregroundStyle(Theme.Palette.ink)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Back to room \(active.code). \(active.detail)")
        .accessibilityIdentifier("roomEntry.active")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

private struct EntryPreview: View {
    let state: RoomEntryViewState
    var body: some View {
        ScrollView { RoomEntryContent(state: state).padding(.horizontal, Theme.Spacing.margin) }.paperBackground()
    }
}

#Preview("Ready · light") { EntryPreview(state: RoomFlowFixtures.entryReady) }
#Preview("Ready · dark") { EntryPreview(state: RoomFlowFixtures.entryReady).previewDark() }
#Preview("Ready · AX3") { EntryPreview(state: RoomFlowFixtures.entryReady).previewLargeType() }
#Preview("Opening · light") { EntryPreview(state: RoomFlowFixtures.entryOpening) }
#Preview("Active · light") { EntryPreview(state: RoomFlowFixtures.entryActive) }
#Preview("Error · light") { EntryPreview(state: RoomFlowFixtures.entryError) }
