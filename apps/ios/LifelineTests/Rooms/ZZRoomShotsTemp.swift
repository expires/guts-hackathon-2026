import SwiftUI
import Testing
import UIKit
@testable import Lifeline

// TEMPORARY (W9): renders screenshots for the report. Removed after the run.
@MainActor
@Suite("W9 room shots")
struct ZZRoomShotsTemp {
    private func save(_ view: some View, _ name: String) async {
        let window = UIWindow(frame: CGRect(x: 0, y: 0, width: 402, height: 874))
        window.rootViewController = UIHostingController(rootView: view)
        window.makeKeyAndVisible()
        try? await Task.sleep(for: .milliseconds(600))
        window.layoutIfNeeded()
        let image = UIGraphicsImageRenderer(bounds: window.bounds).image { _ in
            window.drawHierarchy(in: window.bounds, afterScreenUpdates: true)
        }
        try? image.pngData()?.write(to: URL(fileURLWithPath: "/private/tmp/claude-501/-Users-ash-Workspace-dyhtg/d2613979-29cc-4f7b-8a9a-40abef46e06e/scratchpad/shots/w9-\(name).png"))
        window.isHidden = true
    }

    @Test func render() async {
        await save(GamePickerView(state: RoomFlowFixtures.pickerGames), "picker-games")
        await save(GamePickerView(state: RoomFlowFixtures.pickerStudents), "picker-students")
        await save(GamePickerView(state: RoomFlowFixtures.pickerQuiz), "picker-quiz")
        await save(RoomLobbyView(state: RoomFlowFixtures.lobbyQuickHost), "lobby-host")
        await save(RoomLobbyView(state: RoomFlowFixtures.lobbyQuickGuest), "lobby-guest")
    }
}
