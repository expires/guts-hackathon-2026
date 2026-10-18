// Rebuilt by W9 for lobby first (ADR 0052, 0059), in the Play-Lobby.dc.html style. First draft by W7.
import SwiftUI

/// Lobby: big QR and short code, faces with a ready tick, the picked game, host Pick and Start.
struct RoomLobbyView: View {
    let state: RoomLobbyViewState
    var actions: RoomLobbyActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: L10n.tr("Your lobby"), leading: HeaderSquareButton(kind: .back, identifier: "room.leave", action: actions.onLeave)) {
                    if state.isSampleData { DemoDataBadge() }
                }
                if let connection = state.connection {
                    RoomConnectionBanner(state: connection, onRetry: actions.onReconnect)
                }
                switch state.phase {
                case .loading:
                    LobbySkeleton()
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onReconnect)
                case .ready:
                    if let room = state.room {
                        content(room)
                    } else {
                        Text("No room yet. Open one from Play.").font(.llBody).foregroundStyle(Theme.Palette.muted)
                    }
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    @ViewBuilder
    private func content(_ room: RoomLobbyViewState.RoomInfo) -> some View {
        // Hero: the QR and, next to it, the 4-digit code, large enough to read aloud (ADR 0064).
        VStack(spacing: Theme.Spacing.m) {
            ViewThatFits(in: .horizontal) {
                HStack(spacing: Theme.Spacing.l) {
                    qr(room, size: 160)
                    code(room)
                }
                VStack(spacing: Theme.Spacing.m) {
                    qr(room, size: 200)
                    code(room)
                }
            }
            Text("Friends scan this, or type the code in Play.")
                .font(.llLabel)
                .foregroundStyle(Theme.Palette.muted)
                .multilineTextAlignment(.center)
            ShareLink(item: URL(string: room.joinURL) ?? URL(string: "lifeline://")!, message: Text(state.shareText)) {
                Text("Share the link").lineLimit(1)
            }
            .buttonStyle(.second)
            .accessibilityIdentifier("room.share")
        }
        .frame(maxWidth: .infinity)
        .padding(Theme.Spacing.l)
        .inkSurface(.hero, hero: true)

        // Players: faces with a ready tick.
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            HStack {
                BlockTitle(text: state.playersTitle.isEmpty ? L10n.tr("Players · \(room.players.count) of \(room.maxPlayers)") : state.playersTitle)
                Text(room.modeLabel).font(.llLabel).foregroundStyle(Theme.Palette.muted).lineLimit(1)
            }
            FlowRow(spacing: Theme.Spacing.m) {
                ForEach(room.players) { player in
                    LobbyFace(player: player)
                }
            }
        }

        if let game = state.game {
            HStack(spacing: Theme.Spacing.m) {
                LLIconImage(LLIcon(rawValue: game.icon) ?? .lesson, size: 40)
                VStack(alignment: .leading, spacing: 2) {
                    Text(game.title).font(.llTitle)
                    Text(game.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(Theme.Spacing.l)
            .inkSurface(.card)
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("room.game")
        }

        if state.canReady {
            Button(action: actions.onReady) {
                HStack(spacing: 10) {
                    LLIconImage(.check, size: 24)
                    Text("I'm ready").lineLimit(1)
                }
            }
            .buttonStyle(.main)
            .accessibilityIdentifier("room.ready")
        }
        if state.isHost {
            if state.canPickGame {
                Button(state.game == nil ? L10n.tr("Pick a game") : L10n.tr("Change the game"), action: actions.onPickGame)
                    .buttonStyle(state.game == nil ? AnyButtonStyle(.main) : AnyButtonStyle(.second))
                    .accessibilityIdentifier("room.pickGame")
            }
            if state.game != nil {
                Button(action: actions.onStart) {
                    Text(state.startTitle).lineLimit(1).minimumScaleFactor(0.7)
                }
                .buttonStyle(.main)
                .disabled(!state.canStart)
                .accessibilityIdentifier("room.start")
            }
        } else if !state.waitingText.isEmpty {
            Text(state.waitingText)
                .font(.llBody)
                .foregroundStyle(Theme.Palette.muted)
                .frame(maxWidth: .infinity, alignment: .center)
                .accessibilityIdentifier("room.waiting")
        }
    }

    private func qr(_ room: RoomLobbyViewState.RoomInfo, size: CGFloat) -> some View {
        RoomQRImage(png: room.qrPNG, size: size)
            .accessibilityLabel(L10n.tr("QR code for room \(room.code). Friends scan it in Play, Join a game."))
            .accessibilityIdentifier("room.qr")
    }

    private func code(_ room: RoomLobbyViewState.RoomInfo) -> some View {
        VStack(spacing: Theme.Spacing.xs) {
            Text("Room code").llEyebrow()
            Text(room.code)
                .font(.llHero)
                .scaleEffect(1.4)
                .padding(.vertical, Theme.Spacing.s)
                .tracking(6)
                .monospacedDigit()
                .lineLimit(1)
                .minimumScaleFactor(0.6)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(L10n.tr("Room code \(room.code.map(String.init).joined(separator: " "))"))
        .accessibilityIdentifier("room.codeLabel")
    }
}

/// Face, name and a ready tick.
struct LobbyFace: View {
    let player: RoomLobbyViewState.Player

    var body: some View {
        VStack(spacing: Theme.Spacing.xs) {
            ZStack(alignment: .bottomTrailing) {
                LLIconImage(LLIcon(rawValue: player.face) ?? .faceTeen, size: 48)
                    .frame(width: 60, height: 60)
                    .inkSurface(.badge, fill: player.isMe ? Theme.Palette.family : Theme.Palette.surface)
                    .opacity(player.isConnected ? 1 : 0.5)
                if player.isReady {
                    LLIconImage(.check, size: 24)
                        .frame(width: 28, height: 28)
                        .background(Circle().fill(Theme.Palette.money))
                        .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: Theme.chipOutline))
                        .offset(x: 6, y: 6)
                        .accessibilityHidden(true)
                }
            }
            Text(player.isMe ? L10n.tr("You") : player.name).font(.llLabelBold).lineLimit(1)
            Text(player.isHost ? L10n.tr("Host") : player.statusText).font(.llLabel).foregroundStyle(Theme.Palette.muted).lineLimit(1)
        }
        .frame(width: 76)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(spoken(player))
        .accessibilityIdentifier("room.player.\(player.id)")
    }
}

extension LobbyFace {
    fileprivate func spoken(_ player: RoomLobbyViewState.Player) -> String {
        let name = player.isMe ? L10n.tr("You") : player.name
        return player.isHost ? L10n.tr("\(name), host, \(player.statusText)") : L10n.tr("\(name), \(player.statusText)")
    }
}

/// Lets one button pick its style at run time.
struct AnyButtonStyle: ButtonStyle {
    private let make: (Configuration) -> AnyView

    init<S: ButtonStyle>(_ style: S) {
        make = { AnyView(style.makeBody(configuration: $0)) }
    }

    func makeBody(configuration: Configuration) -> some View { make(configuration) }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Host, no game · light") { RoomLobbyView(state: RoomFlowFixtures.lobbyHostNoGame) }
#Preview("Host · light") { RoomLobbyView(state: RoomFlowFixtures.lobbyHost) }
#Preview("Host · dark") { RoomLobbyView(state: RoomFlowFixtures.lobbyHost).previewDark() }
#Preview("Host · AX3") { RoomLobbyView(state: RoomFlowFixtures.lobbyHost).previewLargeType() }
#Preview("Guest · light") { RoomLobbyView(state: RoomFlowFixtures.lobbyGuest) }
#Preview("Guest · dark") { RoomLobbyView(state: RoomFlowFixtures.lobbyGuest).previewDark() }
#Preview("Reconnecting · light") { RoomLobbyView(state: RoomFlowFixtures.lobbyReconnecting) }
#Preview("Quick Life host · light") { RoomLobbyView(state: RoomFlowFixtures.lobbyQuickHost) }
#Preview("Quick Life host · dark") { RoomLobbyView(state: RoomFlowFixtures.lobbyQuickHost).previewDark() }
#Preview("Quick Life guest · light") { RoomLobbyView(state: RoomFlowFixtures.lobbyQuickGuest) }
#Preview("Quick Life guest · AX3") { RoomLobbyView(state: RoomFlowFixtures.lobbyQuickGuest).previewLargeType() }
