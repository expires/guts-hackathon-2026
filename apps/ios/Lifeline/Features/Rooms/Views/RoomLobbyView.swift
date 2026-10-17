import SwiftUI
import UIKit

/// "Same Life" lobby: create or join a room, share the code, wait for players.
struct RoomLobbyView: View {
    let state: RoomLobbyViewState
    var actions: RoomLobbyActions = .noop

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                    switch state.phase {
                    case let .loading(loading):
                        LoadingStateView(state: loading)
                    case let .failed(error):
                        ErrorStateView(state: error, onRetry: actions.onJoin)
                    case .ready:
                        if let room = state.room {
                            roomContent(room)
                        } else {
                            entry
                        }
                    }
                }
                .padding(Theme.Spacing.l)
            }
            .navigationTitle("Same Life")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Leave", action: actions.onLeave)
                        .accessibilityIdentifier("room.leave")
                }
            }
        }
    }

    private var entry: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            Text("Everyone plays the same life with the same events. Who handles it best?")
                .foregroundStyle(.secondary)
            GlassEffectContainer(spacing: Theme.Spacing.s) {
                VStack(spacing: Theme.Spacing.s) {
                    ForEach([("duel", "Duel", "2 players"), ("group", "Group", "Up to 8 players"), ("class", "Class", "A host runs the room")], id: \.0) { mode in
                        Button { actions.onCreate(mode.0) } label: {
                            VStack(alignment: .leading) {
                                Text("New \(mode.1)").font(.headline)
                                Text(mode.2).font(.subheadline).foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
                        }
                        .buttonStyle(.glass)
                        .accessibilityIdentifier("room.create.\(mode.0)")
                    }
                }
            }
            SectionTitle(text: "Join with a code")
            HStack {
                TextField("Room code", text: Binding(get: { state.joinCode }, set: actions.onJoinCodeChange))
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                    .font(.title2.monospaced())
                    .frame(minHeight: Theme.minTarget)
                    .accessibilityIdentifier("room.code")
                Button("Join", action: actions.onJoin)
                    .buttonStyle(.glassProminent)
                    .disabled(!state.canJoin)
                    .accessibilityIdentifier("room.join")
            }
        }
    }

    private func roomContent(_ room: RoomLobbyViewState.RoomInfo) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            GlassCard {
                VStack(spacing: Theme.Spacing.s) {
                    Text("Room code").font(.subheadline).foregroundStyle(.secondary)
                    Text(room.code)
                        .font(.system(size: 44, weight: .bold, design: .monospaced))
                        .accessibilityIdentifier("room.codeLabel")
                    if let png = room.qrPNG, let image = UIImage(data: png) {
                        Image(uiImage: image)
                            .interpolation(.none)
                            .resizable()
                            .scaledToFit()
                            .frame(width: 160, height: 160)
                            .accessibilityLabel("QR code to join room \(room.code)")
                    }
                    ShareLink(item: room.joinURL) {
                        Label("Share invite", systemImage: "square.and.arrow.up")
                            .frame(minHeight: Theme.minTarget)
                    }
                    Text("\(room.modeLabel) · starts \(String(room.startYear))")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
            }
            SectionTitle(text: "Players \(room.players.count) of \(room.maxPlayers)")
            ForEach(room.players) { player in
                HStack {
                    Image(systemName: "person.crop.circle.fill").accessibilityHidden(true)
                    Text(player.isMe ? "\(player.name) (you)" : player.name)
                    Spacer()
                    if player.isHost {
                        Text("Host").font(.caption).foregroundStyle(.secondary)
                    }
                }
                .frame(minHeight: Theme.minTarget)
                .accessibilityElement(children: .combine)
            }
            Text(room.statusLabel).font(.footnote).foregroundStyle(.secondary)
            if state.isHost {
                PrimaryButton(title: "Start", systemImage: "play.fill", action: actions.onStart)
                    .disabled(!state.canStart)
                    .accessibilityIdentifier("room.start")
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Entry · light") {
    RoomLobbyView(state: Fixtures.Rooms.entry)
}

#Preview("Entry · dark") {
    RoomLobbyView(state: Fixtures.Rooms.entry).previewDark()
}

#Preview("Entry · AX3") {
    RoomLobbyView(state: Fixtures.Rooms.entry).previewLargeType()
}

#Preview("Lobby, 4 players · light") {
    RoomLobbyView(state: Fixtures.Rooms.lobbyFour)
}

#Preview("Lobby, 4 players · dark") {
    RoomLobbyView(state: Fixtures.Rooms.lobbyFour).previewDark()
}

#Preview("Lobby, 4 players · AX3") {
    RoomLobbyView(state: Fixtures.Rooms.lobbyFour).previewLargeType()
}

#Preview("Joining · light") {
    RoomLobbyView(state: Fixtures.Rooms.joining)
}

#Preview("Joining · dark") {
    RoomLobbyView(state: Fixtures.Rooms.joining).previewDark()
}

#Preview("Joining · AX3") {
    RoomLobbyView(state: Fixtures.Rooms.joining).previewLargeType()
}
