import SwiftUI

/// Playground gallery entries for the W9 room screens. The gallery shows them under ids "w9rooms.*".
@MainActor
enum RoomsPlayground {
    struct Entry: Identifiable {
        var id: String
        var title: String
        var detail: String
    }

    static let entries: [Entry] = [
        .init(id: "w9rooms.entry", title: "Play with friends", detail: "Open or join"),
        .init(id: "w9rooms.entryActive", title: "Play with friends", detail: "Back to your room"),
        .init(id: "w9rooms.entryError", title: "Play with friends", detail: "Join error"),
        .init(id: "w9rooms.lobbyNoGame", title: "Lobby", detail: "Host, no game yet"),
        .init(id: "w9rooms.lobbyHost", title: "Lobby", detail: "Host, Money Quiz picked"),
        .init(id: "w9rooms.lobbyGuest", title: "Lobby", detail: "Guest, not ready"),
        .init(id: "w9rooms.lobbyReconnecting", title: "Lobby", detail: "Reconnecting"),
        .init(id: "w9rooms.lobbyQuickHost", title: "Lobby", detail: "Host, Quick Life, no ready step"),
        .init(id: "w9rooms.lobbyQuickGuest", title: "Lobby", detail: "Guest, Quick Life, waiting for host"),
        .init(id: "w9rooms.pickerGames", title: "Pick a game", detail: "Quick Life first"),
        .init(id: "w9rooms.pickerStudents", title: "Pick a game", detail: "Quick Life students"),
        .init(id: "w9rooms.pickerQuiz", title: "Pick a game", detail: "Money Quiz"),
        .init(id: "w9rooms.quiz", title: "Money Quiz", detail: "Question"),
        .init(id: "w9rooms.quizReveal", title: "Money Quiz", detail: "Reveal"),
        .init(id: "w9rooms.decision", title: "Same Decision", detail: "Open"),
        .init(id: "w9rooms.decisionReveal", title: "Same Decision", detail: "Reveal"),
        .init(id: "w9rooms.gameOver", title: "Final ranking", detail: "Money Quiz"),
        .init(id: "w9rooms.liveAge", title: "Same Life", detail: "Age up"),
        .init(id: "w9rooms.liveEvent", title: "Same Life", detail: "Open event"),
        .init(id: "w9rooms.resultQuick", title: "Same Life results", detail: "Quick Life card"),
        .init(id: "w9rooms.resultPending", title: "Same Life results", detail: "2 still playing"),
        .init(id: "w9rooms.circles", title: "Circles", detail: "List"),
        .init(id: "w9rooms.circleDetail", title: "Circles", detail: "Members and recap"),
        .init(id: "w9rooms.scanner", title: "QR scanner", detail: "No camera"),
        .init(id: "w9rooms.codeEntry", title: "Type a code", detail: "Join"),
        .init(id: "w9rooms.simulated", title: "Play with friends", detail: "Live mock, 3 friends"),
    ]

    @ViewBuilder
    static func view(_ id: String) -> some View {
        switch id {
        case "w9rooms.entry": entry(RoomFlowFixtures.entryReady)
        case "w9rooms.entryActive": entry(RoomFlowFixtures.entryActive)
        case "w9rooms.entryError": entry(RoomFlowFixtures.entryError)
        case "w9rooms.lobbyNoGame": RoomLobbyView(state: RoomFlowFixtures.lobbyHostNoGame)
        case "w9rooms.lobbyHost": RoomLobbyView(state: RoomFlowFixtures.lobbyHost)
        case "w9rooms.lobbyGuest": RoomLobbyView(state: RoomFlowFixtures.lobbyGuest)
        case "w9rooms.lobbyReconnecting": RoomLobbyView(state: RoomFlowFixtures.lobbyReconnecting)
        case "w9rooms.lobbyQuickHost": RoomLobbyView(state: RoomFlowFixtures.lobbyQuickHost)
        case "w9rooms.lobbyQuickGuest": RoomLobbyView(state: RoomFlowFixtures.lobbyQuickGuest)
        case "w9rooms.pickerGames": GamePickerView(state: RoomFlowFixtures.pickerGames)
        case "w9rooms.pickerStudents": GamePickerView(state: RoomFlowFixtures.pickerStudents)
        case "w9rooms.pickerQuiz": GamePickerView(state: RoomFlowFixtures.pickerQuiz)
        case "w9rooms.quiz": QuizView(state: RoomFlowFixtures.quizQuestion)
        case "w9rooms.quizReveal": QuizView(state: RoomFlowFixtures.quizReveal)
        case "w9rooms.decision": DecisionView(state: RoomFlowFixtures.decisionOpen)
        case "w9rooms.decisionReveal": DecisionView(state: RoomFlowFixtures.decisionReveal)
        case "w9rooms.gameOver": GameOverView(state: RoomFlowFixtures.gameOver)
        case "w9rooms.liveAge": RoomLiveView(state: RoomFlowFixtures.liveAge)
        case "w9rooms.liveEvent": RoomLiveView(state: RoomFlowFixtures.liveEvent)
        case "w9rooms.resultQuick": RoomResultView(state: RoomFlowFixtures.resultQuickLife)
        case "w9rooms.resultPending": RoomResultView(state: RoomFlowFixtures.resultPending)
        case "w9rooms.circles": scroll(CirclesContent(state: RoomFlowFixtures.circles))
        case "w9rooms.circleDetail": scroll(CirclesContent(state: RoomFlowFixtures.circleDetail))
        case "w9rooms.scanner": RoomScannerView(state: RoomFlowFixtures.scannerUnavailable)
        case "w9rooms.codeEntry": RoomCodeEntryView(state: RoomFlowFixtures.entry(joinCode: "K7Q2ZP"))
        case "w9rooms.simulated": RoomLobbyScreen(session: GameSession(client: MockClient()), onLeave: {})
        default: Text("Unknown room entry \(id)").font(.llBody)
        }
    }

    private static func scroll(_ content: some View) -> some View {
        ScrollView { content.padding(.horizontal, Theme.Spacing.margin).padding(.vertical, Theme.Spacing.m) }.paperBackground()
    }

    private static func entry(_ state: RoomEntryViewState) -> some View {
        ScrollView {
            RoomEntryContent(state: state)
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.vertical, Theme.Spacing.m)
        }
        .paperBackground()
    }
}
