import Foundation

/// Pure mapping from contract values to room view states. Fixtures and tests call it directly.
@MainActor
enum RoomMapping {
    /// Faces by seat. The design has no avatar in the contract, so seats get a fixed face.
    static let faces = ["face-teen", "face-woman-puff", "face-man-beard", "face-teen-hijab", "face-man-glasses", "face-blue-hair", "face-older-woman", "face-older-man"]

    static func face(seat: Int) -> String { faces[seat % faces.count] }

    // MARK: Connection

    static func connection(_ link: RoomSession.Link) -> RoomConnectionState? {
        switch link {
        case .idle, .live: nil
        case .connecting: .init(kind: .connecting, text: "Connecting to the room", canRetry: false)
        case let .reconnecting(attempt): .init(kind: .reconnecting, text: "Reconnecting (try \(attempt))", canRetry: false)
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
        qrPNG: Data?,
        isSampleData: Bool
    ) -> RoomLobbyViewState {
        let me = room.players.first { $0.id == myID }
        let isHost = me?.isHost ?? false
        let players = room.players.enumerated().map { seat, player in
            let connected = player.connected ?? true
            let ready = isReady(player)
            return RoomLobbyViewState.Player(
                id: player.id, name: player.name, isHost: player.isHost, isMe: player.id == myID,
                face: face(seat: seat),
                statusText: !connected ? "Away" : (ready ? "Ready" : "Not ready"),
                isReady: ready && connected,
                isConnected: connected
            )
        }
        let readyCount = players.filter(\.isReady).count
        let host = room.players.first { $0.isHost }
        let game = GameMapping.gameCard(room: room, paths: paths)
        let info = RoomLobbyViewState.RoomInfo(
            code: room.code,
            modeLabel: readyCount <= 2 ? "2 players: a duel" : "\(readyCount) players: a group game",
            joinURL: room.joinUrl,
            qrPNG: qrPNG,
            players: players,
            maxPlayers: room.maxPlayers,
            statusLabel: room.status == .lobby ? "Waiting for players" : room.status.rawValue.capitalized,
            startYear: room.gameStartYear
        )
        let startTitle: String
        if game == nil {
            startTitle = "Pick a game first"
        } else if readyCount < 2 {
            startTitle = "Waiting for players"
        } else {
            startTitle = "Start with \(readyCount) players"
        }
        return RoomLobbyViewState(
            phase: .ready,
            room: info,
            joinCode: "",
            canJoin: false,
            isHost: isHost,
            canStart: isHost && room.status == .lobby && readyCount >= 2 && game != nil && link == .live,
            playersTitle: "Players · \(room.players.count) of \(room.maxPlayers)",
            startTitle: startTitle,
            isSampleData: isSampleData,
            connection: connection(link),
            canReady: me != nil && !isHost && me?.ready != true && link == .live,
            isMeReady: me.map(isReady) ?? false,
            waitingText: isHost ? "" : (game == nil ? "Waiting for \(host?.name ?? "the host") to pick a game" : "Waiting for \(host?.name ?? "the host") to start"),
            shareText: "Play with me in \(Brand.productName). Room \(room.code): \(room.joinUrl)",
            game: game,
            canPickGame: isHost && room.status == .lobby && link == .live
        )
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
        var caption = "Age · INDEX."
        if life != nil { caption += ahead == 0 ? " You lead the room." : " \(ahead) ahead of you." }
        if !finished.isEmpty { caption += " Finished: \(finished.joined(separator: ", "))." }
        guard let life else {
            return RoomLiveViewState(
                name: "Your life", face: "face-teen", detail: "Room \(room.code)", bank: 0,
                rivals: strip, rivalCaption: caption, storyTitle: "Same start for everyone", storyLines: [],
                lessonTitle: "", stats: [], isSampleData: isSampleData, connection: connection(link),
                waitingText: "Starting your life", canFinish: false
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
            detail: "Age \(life.age) · Room \(room.code)",
            bank: life.finances.cash + life.finances.savings,
            rivals: strip,
            rivalCaption: caption,
            storyTitle: "\(life.year) · Age \(life.age)",
            storyLines: lines,
            lessonTitle: "",
            stats: [
                .init(id: "happiness", icon: "happiness", title: "Happiness", value: life.stats.happiness),
                .init(id: "money", icon: "savings", title: "Money", value: life.stats.money),
            ],
            isSampleData: isSampleData,
            connection: connection(link),
            event: done ? nil : event,
            ageTitle: done || event != nil ? nil : "Age up to \(life.age + 1)",
            isBusy: isBusy,
            waitingText: done ? "Your run is over" : nil,
            canFinish: !done || me?.finished != true,
            canOpenLife: !done
        )
    }

    // MARK: Results

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
        isSampleData: Bool
    ) -> RoomResultViewState {
        let seats = Dictionary(uniqueKeysWithValues: room.players.enumerated().map { ($1.id, $0) })
        let ranked = room.players.sorted { ($0.index ?? 0, $0.netWorth ?? 0) > ($1.index ?? 0, $1.netWorth ?? 0) }
        let rows = ranked.enumerated().map { offset, player in
            let isMe = player.id == myID
            let life = isMe ? myLife : player.lifeId.flatMap { rivalLives[$0] }
            let finished = player.finished ?? false
            return RoomResultViewState.Row(
                id: player.id, rank: offset + 1, name: player.name,
                index: player.index ?? 100, netWorth: player.netWorth ?? 0,
                ribbons: life?.ribbons.count ?? 0, isMe: isMe,
                face: face(seat: seats[player.id] ?? 0),
                note: finished ? "" : "Still playing",
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
        let winnerLine = winner.map { "\($0.isMe ? "You" : $0.name) · INDEX \(Int($0.index.rounded()))" } ?? ""
        let me = rows.first { $0.isMe }
        let lastYear = room.players.compactMap(\.year).max() ?? room.gameStartYear
        var splitsNote = ""
        if splits.isEmpty {
            splitsNote = rivals.isEmpty
                ? "Other players' choices are not available yet."
                : "Your lives made the same choices."
        }
        let share = [
            "Same Life room \(room.code): \(winnerLine) leads.",
            me.map { "I came \($0.rank) of \(rows.count) with INDEX \(Int($0.index.rounded()))." },
        ].compactMap { $0 }.joined(separator: " ")
        return RoomResultViewState(
            rows: rows,
            splits: splits,
            winnerName: winner?.name ?? "",
            subtitle: "\(room.code) · \(room.gameStartYear) to \(lastYear)",
            winnerLine: winnerLine,
            winnerNote: "",
            winnerNetWorth: winner?.netWorth,
            earned: (myLife?.ribbons ?? []).map { .init(icon: "ribbon", text: $0.title) },
            shareText: share,
            isSampleData: isSampleData,
            pendingText: pending == 0 ? "" : (pending == 1 ? "1 player still playing" : "\(pending) players still playing"),
            splitsNote: splitsNote,
            connection: connection(link)
        )
    }
}
