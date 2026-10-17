// Rebuilt for ADR 0026 (Play-Lobby.dc.html) by W7.
import SwiftUI

/// "Same Life" lobby as a full screen: create or join a room, share the code, wait for players.
struct RoomLobbyView: View {
    let state: RoomLobbyViewState
    var actions: RoomLobbyActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: "Same Life", leading: HeaderSquareButton(kind: .back, identifier: "room.leave", action: actions.onLeave)) {
                    if state.isSampleData { DemoDataBadge() }
                }
                RoomLobbyContent(state: state, actions: actions)
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }
}

/// Lobby body. The Play tab shows it under its "Rooms" segment; `RoomLobbyView` wraps it as a screen.
struct RoomLobbyContent: View {
    let state: RoomLobbyViewState
    var actions: RoomLobbyActions = .noop

    var body: some View {
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
        .foregroundStyle(Theme.Palette.ink)
    }

    private var entry: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            Text("Everyone plays the same life with the same events. Who handles it best?")
                .font(.llBody)
            VStack(spacing: Theme.Spacing.s) {
                ForEach([("duel", "Duel", "2 players"), ("group", "Group", "Up to 8 players"), ("class", "Class", "A host runs the room")], id: \.0) { mode in
                    Button { actions.onCreate(mode.0) } label: {
                        HStack {
                            Text("New \(mode.1)").lineLimit(1)
                            Spacer(minLength: Theme.Spacing.s)
                            Text(mode.2).font(.llLabel).lineLimit(1).minimumScaleFactor(0.7)
                        }
                    }
                    .buttonStyle(.second)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .accessibilityIdentifier("room.create.\(mode.0)")
                }
            }
            BlockTitle(text: "Join with a code")
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
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .frame(width: 104)
                    .disabled(!state.canJoin)
                    .accessibilityIdentifier("room.join")
            }
        }
    }

    private func roomContent(_ room: RoomLobbyViewState.RoomInfo) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            HStack(spacing: Theme.Spacing.m) {
                VStack(alignment: .leading, spacing: 0) {
                    Text("Same Life room").font(.llLabelBold).foregroundStyle(Theme.Palette.muted)
                    Text(room.code)
                        .font(.llHero)
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                        .accessibilityIdentifier("room.codeLabel")
                }
                Spacer(minLength: 0)
                ShareLink(item: room.joinURL) { Text("Share").lineLimit(1) }
                    .buttonStyle(.second)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .frame(width: 110)
                    .accessibilityLabel("Share the room code \(room.code)")
                    .accessibilityIdentifier("room.share")
            }
            .padding(Theme.Spacing.l)
            .inkSurface(.hero, hero: true)

            if !state.lifeLine.isEmpty {
                InkCard(shape: .cardAlt) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        Text("Everyone plays the same life").font(.llBodyBold)
                        HStack(alignment: .top, spacing: Theme.Spacing.m) {
                            LLIconImage(LLIcon(rawValue: state.lifeFace) ?? .facePriya, size: 48)
                            Text(state.lifeLine).font(.llBody).fixedSize(horizontal: false, vertical: true)
                        }
                        Text(state.rulesLine).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                }
                .accessibilityElement(children: .combine)
            }

            VStack(alignment: .leading, spacing: 0) {
                BlockTitle(text: state.playersTitle.isEmpty ? "Players \(room.players.count) of \(room.maxPlayers)" : state.playersTitle)
                    .padding(.bottom, Theme.Spacing.xs)
                ForEach(Array(room.players.enumerated()), id: \.element.id) { offset, player in
                    if offset > 0 { RuleDivider() }
                    HStack(spacing: Theme.Spacing.m) {
                        LLIconImage(LLIcon(rawValue: player.face) ?? .faceTeen, size: 32)
                        HStack(spacing: 0) {
                            Text(player.name).font(player.isMe ? .llBodyBold : .llBody)
                            if player.isHost { Text(" · host").font(.llBody) }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        if player.isReady {
                            Chip(text: player.statusText, fill: Theme.Palette.money)
                        } else {
                            Text(player.statusText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                    }
                    .frame(minHeight: Theme.minTarget)
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("room.player.\(player.id)")
                }
            }
            if state.isHost {
                Button(action: actions.onStart) {
                    Text(state.startTitle).lineLimit(1).minimumScaleFactor(0.7)
                }
                .buttonStyle(.main)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .disabled(!state.canStart)
                .accessibilityIdentifier("room.start")
            } else {
                Text(room.statusLabel).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Demo lobby · light") { RoomLobbyView(state: RoomsFixtures.lobby) }
#Preview("Demo lobby · dark") { RoomLobbyView(state: RoomsFixtures.lobby).previewDark() }
#Preview("Demo lobby · AX3") { RoomLobbyView(state: RoomsFixtures.lobby).previewLargeType() }
#Preview("Entry · light") { RoomLobbyView(state: Fixtures.Rooms.entry) }
#Preview("Entry · dark") { RoomLobbyView(state: Fixtures.Rooms.entry).previewDark() }
#Preview("Entry · AX3") { RoomLobbyView(state: Fixtures.Rooms.entry).previewLargeType() }
#Preview("Joining · light") { RoomLobbyView(state: Fixtures.Rooms.joining) }
#Preview("Joining · dark") { RoomLobbyView(state: Fixtures.Rooms.joining).previewDark() }
#Preview("Joining · AX3") { RoomLobbyView(state: Fixtures.Rooms.joining).previewLargeType() }
