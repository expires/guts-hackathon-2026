import Foundation

/// Pure mapping from contract values to room view states. Fixtures and tests call it directly.
@MainActor
enum RoomMapping {
    /// Faces by seat. The design has no avatar in the contract, so seats get a fixed face.
    static let faces = ["face-teen", "face-woman-puff", "face-man-beard", "face-teen-hijab", "face-man-glasses", "face-blue-hair", "face-older-woman", "face-older-man"]

    static func face(seat: Int) -> String { faces[seat % faces.count] }

    /// A Same Life room played as a Quick Life (the server default when the option is missing).
    nonisolated static func isQuickLife(_ room: Room) -> Bool {
        RoomGameKind(room: room.game) == .sameLife && (room.options?.quick ?? true)
    }

    /// Server rule (routes/rooms.py `_is_quick_life`): a Quick Life round, or a lobby with no game picked yet
    /// that is not a preset room. The host's Start counts every seated player as ready, so nobody sends "ready".
    nonisolated static func joiningCountsAsReady(_ room: Room) -> Bool {
        if room.game == nil { return room.presetId == nil }
        return isQuickLife(room)
    }

    // MARK: Connection

    static func connection(_ link: RoomSession.Link) -> RoomConnectionState? {
        switch link {
        case .idle, .live: nil
        case .connecting: .init(kind: .connecting, text: L10n.tr("Connecting to the room"), canRetry: false)
        case let .reconnecting(attempt): .init(kind: .reconnecting, text: L10n.tr("Reconnecting (try \(attempt))"), canRetry: false)
        case let .offline(message): .init(kind: .offline, text: message, canRetry: true)
        }
    }

    // MARK: Lobby

    static func isReady(_ player: RoomWire.Player) -> Bool { player.isHost || player.ready == true }

    static func lobby(
        room: Room,
        myID: String?,
        link: RoomSession.Link,
        paths: [PlayWire.Path] = [],
        students: [PlayWire.Student] = [],
        qrPNG: Data?,
        isSampleData: Bool
    ) -> RoomLobbyViewState {
        let me = room.players.first { $0.id == myID }
        let isHost = me?.isHost ?? false
        let joinIsReady = joiningCountsAsReady(room)
        let players = room.players.enumerated().map { seat, player in
            let connected = player.connected ?? true
            let ready = joinIsReady || isReady(player)
            return RoomLobbyViewState.Player(
                id: player.id, name: player.name, isHost: player.isHost, isMe: player.id == myID,
                face: face(seat: seat),
                statusText: !connected ? L10n.tr("Away") : (ready ? L10n.tr("Ready") : L10n.tr("Not ready")),
                isReady: ready && connected,
                isConnected: connected
            )
        }
        let readyCount = players.filter(\.isReady).count
        // Server rule (routes/rooms.py "start"): every seated player is ready (the host counts as ready),
        // and at least 2 players. A player who is away still counts and must be ready.
        // Quick Life: joining counts as ready, so 2 seated players are enough.
        let notReady = joinIsReady ? 0 : room.players.filter { !isReady($0) }.count
        let everyoneReady = notReady == 0 && room.players.count >= 2
        let host = room.players.first { $0.isHost }
        let game = GameMapping.gameCard(room: room, paths: paths, students: students)
        let info = RoomLobbyViewState.RoomInfo(
            code: room.code,
            modeLabel: readyCount <= 2 ? L10n.tr("2 players: a duel") : L10n.tr("\(readyCount) players: a group game"),
            joinURL: room.joinUrl,
            qrPNG: qrPNG,
            players: players,
            maxPlayers: room.maxPlayers,
            statusLabel: room.status == .lobby ? L10n.tr("Waiting for players") : (room.status == .playing ? L10n.tr("Playing") : L10n.tr("Finished")),
            startYear: room.gameStartYear
        )
        let startTitle: String
        if game == nil {
            startTitle = L10n.tr("Pick a game first")
        } else if room.players.count < 2 {
            startTitle = L10n.tr("Waiting for players")
        } else if notReady > 0 {
            startTitle = L10n.tr("Waiting for \(notReady) to get ready")
        } else {
            startTitle = L10n.tr("Start with \(room.players.count) players")
        }
        return RoomLobbyViewState(
            phase: .ready,
            room: info,
            joinCode: "",
            canJoin: false,
            isHost: isHost,
            canStart: isHost && room.status == .lobby && everyoneReady && game != nil && link == .live,
            playersTitle: L10n.tr("Players · \(room.players.count) of \(room.maxPlayers)"),
            startTitle: startTitle,
            isSampleData: isSampleData,
            connection: connection(link),
            canReady: !joinIsReady && me != nil && !isHost && me?.ready != true && link == .live,
            isMeReady: joinIsReady ? me != nil : (me.map(isReady) ?? false),
            waitingText: isHost ? "" : waiting(host: host?.name, picked: game != nil),
            shareText: L10n.tr("Play with me in \(Brand.productName). Room \(room.code): \(room.joinUrl)"),
            game: game,
            canPickGame: isHost && room.status == .lobby && link == .live
        )
    }

    private static func waiting(host: String?, picked: Bool) -> String {
        guard let host else { return picked ? L10n.tr("Waiting for the host to start") : L10n.tr("Waiting for the host to pick a game") }
        return picked ? L10n.tr("Waiting for \(host) to start") : L10n.tr("Waiting for \(host) to pick a game")
    }

    // MARK: Live

    static func rivals(room: Room, myID: String?) -> RivalStripViewState {
        RivalStripViewState(rivals: room.players.enumerated().map { seat, player in
            .init(
                id: player.id, name: player.name, age: player.age, netWorth: player.netWorth, index: player.index,
                isMe: player.id == myID, finished: player.finished ?? false, face: face(seat: seat),
                isConnected: player.connected ?? true
            )
        })
    }

    static func live(
        room: Room,
        myID: String?,
        life: Life?,
        link: RoomSession.Link,
        isBusy: Bool,
        isSampleData: Bool
    ) -> RoomLiveViewState {
        let strip = rivals(room: room, myID: myID)
        let ahead = room.players.filter { $0.id != myID && ($0.index ?? 0) > (life?.index.value ?? 0) }.count
        let finished = room.players.filter { $0.id != myID && $0.finished == true }.map(\.name)
        var parts = [L10n.tr("Age · INDEX.")]
        if life != nil { parts.append(ahead == 0 ? L10n.tr("You lead the room.") : L10n.tr("\(ahead) ahead of you.")) }
        if !finished.isEmpty { parts.append(L10n.tr("Finished: \(finished.joined(separator: ", ")).")) }
        let caption = parts.joined(separator: " ")
        guard let life else {
            return RoomLiveViewState(
                name: L10n.tr("Your life"), face: "face-teen", detail: L10n.tr("Room \(room.code)"), bank: 0,
                rivals: strip, rivalCaption: caption, storyTitle: L10n.tr("Same start for everyone"), storyLines: [],
                lessonTitle: "", stats: [], isSampleData: isSampleData, connection: connection(link),
                waitingText: L10n.tr("Starting your life"), canFinish: false
            )
        }
        let recent = life.history.filter { $0.year == life.year }.map(\.text)
        let lines = recent.isEmpty ? Array(life.history.suffix(2).map(\.text)) : recent
        let event = life.pendingEvents.first.map { event in
            RoomLiveViewState.Event(id: event.id, title: event.title, text: event.text, choices: event.choices.map { .init(id: $0.id, label: $0.label) })
        }
        let me = room.players.first { $0.id == myID }
        let done = !life.alive || me?.finished == true
        return RoomLiveViewState(
            name: life.character.name,
            face: LLIcon.face(emoji: life.character.emoji).rawValue,
            detail: L10n.tr("Age \(life.age) · Room \(room.code)"),
            bank: life.finances.cash + life.finances.savings,
            rivals: strip,
            rivalCaption: caption,
            storyTitle: L10n.tr("\(String(life.year)) · Age \(life.age)"),
            storyLines: lines,
            lessonTitle: "",
            stats: [
                .init(id: "happiness", icon: "happiness", title: L10n.tr("Happiness"), value: life.stats.happiness),
                .init(id: "money", icon: "savings", title: L10n.tr("Money"), value: life.stats.money),
            ],
            isSampleData: isSampleData,
            connection: connection(link),
            event: done ? nil : event,
            showsAgeUp: !done && event == nil,
            nextAge: life.nextAge(mayBeQuick: isQuickLife(room)),
            isBusy: isBusy,
            waitingText: done ? L10n.tr("Your run is over") : nil,
            canFinish: !done || me?.finished != true,
            canOpenLife: !done && FeatureFlags.showsCutFeatures
        )
    }

    // MARK: Results

    /// Penny's line when the server sends none. Numbers come from the result (INDEX).
    static func winnerTemplate(_ row: RoomResultViewState.Row) -> String {
        let index = Int(row.index.rounded())
        return row.isMe
            ? L10n.tr("You win this Same Life with INDEX \(index). Same events, better choices.")
            : L10n.tr("\(row.name) wins this Same Life with INDEX \(index). Same events, better choices.")
    }

    /// Where your life and each rival's life split: the first decision year with a different choice.
    static func splits(mine: Life, rivals: [(name: String, life: Life)]) -> [RoomResultViewState.Split] {
        rivals.compactMap { rival in
            let theirs = Dictionary(
                rival.life.history.compactMap { entry in entry.choiceId == nil ? nil : (key(entry), entry) },
                uniquingKeysWith: { first, _ in first }
            )
            for entry in mine.history where entry.choiceId != nil {
                guard let other = theirs[key(entry)], other.choiceId != entry.choiceId else { continue }
                return .init(
                    id: "\(rival.name)-\(entry.year)", year: entry.year, age: entry.age,
                    myChoice: entry.text, rivalName: rival.name, rivalChoice: other.text
                )
            }
            return nil
        }
        .sorted { ($0.year, $0.rivalName) < ($1.year, $1.rivalName) }
    }

    /// Decisions match on event and year. Same seed means the same events.
    private static func key(_ entry: YearLog) -> String {
        "\(entry.year)|\(entry.eventId ?? entry.decisionId ?? "")"
    }

    static func result(
        room: Room,
        myID: String?,
        myLife: Life?,
        rivalLives: [String: Life],
        link: RoomSession.Link,
        isSampleData: Bool,
        serverRanking: [PlayWire.Score] = [],
        serverWinnerLine: String? = nil
    ) -> RoomResultViewState {
        let seats = Dictionary(uniqueKeysWithValues: room.players.enumerated().map { ($1.id, $0) })
        // The server's final ranking decides the order (ADR 0064: by result). Before it, order by INDEX.
        let order = Dictionary(serverRanking.map { ($0.playerId, $0.rank) }, uniquingKeysWith: { first, _ in first })
        let ranked = order.isEmpty
            ? room.players.sorted { ($0.index ?? 0, $0.netWorth ?? 0) > ($1.index ?? 0, $1.netWorth ?? 0) }
            : room.players.sorted { (order[$0.id] ?? Int.max, $0.name) < (order[$1.id] ?? Int.max, $1.name) }
        let rows = ranked.enumerated().map { offset, player in
            let isMe = player.id == myID
            let life = isMe ? myLife : player.lifeId.flatMap { rivalLives[$0] }
            let finished = player.finished ?? false
            return RoomResultViewState.Row(
                id: player.id, rank: offset + 1, name: player.name,
                index: player.index ?? 100, netWorth: player.netWorth ?? 0,
                ribbons: life?.ribbons.count ?? 0, isMe: isMe,
                face: face(seat: seats[player.id] ?? 0),
                note: finished ? "" : L10n.tr("Still playing"),
                finished: finished,
                ribbonsKnown: life != nil
            )
        }
        let rivals = room.players.filter { $0.id != myID }.compactMap { player -> (name: String, life: Life)? in
            guard let id = player.lifeId, let life = rivalLives[id] else { return nil }
            return (player.name, life)
        }
        let splits = myLife.map { splits(mine: $0, rivals: rivals) } ?? []
        let winner = rows.first
        let pending = rows.filter { !$0.finished }.count
        let winnerLine = winner.map { $0.isMe ? L10n.tr("You · INDEX \(Int($0.index.rounded()))") : L10n.tr("\($0.name) · INDEX \(Int($0.index.rounded()))") } ?? ""
        let me = rows.first { $0.isMe }
        let lastYear = room.players.compactMap(\.year).max() ?? room.gameStartYear
        var splitsNote = ""
        if splits.isEmpty {
            splitsNote = rivals.isEmpty
                ? L10n.tr("Other players' choices are not available yet.")
                : L10n.tr("Your lives made the same choices.")
        }
        let share = [
            L10n.tr("Same Life room \(room.code): \(winnerLine) leads."),
            me.map { L10n.tr("I came \($0.rank) of \(rows.count) with INDEX \(Int($0.index.rounded())).") },
        ].compactMap { $0 }.joined(separator: " ")
        return RoomResultViewState(
            rows: rows,
            splits: splits,
            winnerName: winner?.name ?? "",
            subtitle: L10n.tr("\(room.code) · \(String(room.gameStartYear)) to \(String(lastYear))"),
            winnerLine: winnerLine,
            winnerNote: "",
            winnerNetWorth: winner?.netWorth,
            earned: (myLife?.ribbons ?? []).map { .init(icon: "ribbon", text: $0.title) },
            shareText: share,
            isSampleData: isSampleData,
            pendingText: pending == 0 ? "" : (pending == 1 ? "1 player still playing" : "\(pending) players still playing"),
            splitsNote: splitsNote,
            pennyLine: pending > 0 ? "" : (serverWinnerLine ?? winner.map(winnerTemplate) ?? ""),
            connection: connection(link)
        )
    }
}
