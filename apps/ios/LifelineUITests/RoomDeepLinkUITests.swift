import XCTest

/// W9 (PENNY_V3_BUILD.md F5): the lobby QR encodes `lifeline://join/CODE`. Opening that link selects Play and
/// opens the room cover on the lobby: with the app running on another tab, and from a cold start.
/// A real iPhone camera scan still needs a person with a phone.
final class RoomDeepLinkUITests: XCTestCase {
    private let link = URL(string: "lifeline://join/1234")!

    override func setUp() {
        continueAfterFailure = false
    }

    /// iOS may ask "Open in Penny?" for a link from outside the app. Tap Open when it does.
    @MainActor
    private func confirmOpenIfAsked() {
        let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
        let open = springboard.buttons["Open"]
        if open.waitForExistence(timeout: 3) { open.tap() }
    }

    @MainActor
    private func attachScreenshot(_ name: String) {
        let shot = XCTAttachment(screenshot: XCUIScreen.main.screenshot())
        shot.name = name
        shot.lifetime = .keepAlways
        add(shot)
    }

    @MainActor
    func testJoinLinkOpensLobbyWhileAppRunsOnMoneyTab() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock"]
        app.launch()
        // The app opens on Money, not Play.
        XCTAssertTrue(app.buttons["tab.money"].waitForExistence(timeout: 10))

        app.open(link)
        confirmOpenIfAsked()

        let code = app.descendants(matching: .any)["room.codeLabel"]
        XCTAssertTrue(code.waitForExistence(timeout: 15), "The join link must open the lobby")
        XCTAssertEqual(code.label, "Room code 1 2 3 4")
        XCTAssertTrue(app.descendants(matching: .any)["room.qr"].exists)
        // A guest in a Quick Life lobby never sees "I'm ready".
        XCTAssertFalse(app.buttons["room.ready"].exists)
        attachScreenshot("Deep link, warm start: lobby")
    }

    @MainActor
    func testJoinLinkOpensRoomFromColdStart() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock"]
        app.launch()
        XCTAssertTrue(app.buttons["tab.money"].waitForExistence(timeout: 10))
        app.terminate()

        // Cold start by the link. Launch arguments do not apply here, so the client follows the build's
        // default: the room cover opens on the lobby (mock) or on the join screen with the join result.
        app.open(link)
        confirmOpenIfAsked()

        let lobby = app.descendants(matching: .any)["room.codeLabel"]
        let entry = app.buttons["room.close"]
        let opened = lobby.waitForExistence(timeout: 20) || entry.exists
        attachScreenshot("Deep link, cold start")
        XCTAssertTrue(opened, "The join link must open the room cover from a cold start")
    }

    /// Host: Play with friends, then Pick a game. Quick Life is first; one tap on a student picks it and
    /// returns to the lobby. With 2 or more players the Start button turns on without any "ready".
    @MainActor
    func testHostPicksQuickLifeStudentInOneTap() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock"]
        app.launch()
        let play = app.buttons["tab.play"]
        XCTAssertTrue(play.waitForExistence(timeout: 10))
        play.tap()
        let friends = app.buttons["play.friends"]
        XCTAssertTrue(friends.waitForExistence(timeout: 10))
        friends.tap()

        let pick = app.buttons["room.pickGame"]
        XCTAssertTrue(pick.waitForExistence(timeout: 15))
        pick.tap()
        let quick = app.buttons["picker.game.quick_life"]
        let quiz = app.buttons["picker.game.quiz"]
        XCTAssertTrue(quick.waitForExistence(timeout: 10))
        XCTAssertLessThan(quick.frame.minY, quiz.frame.minY, "Quick Life must be first")
        XCTAssertFalse(app.buttons["picker.game.same_decision"].exists, "Same Decision is cut")
        attachScreenshot("Picker: games")

        quick.tap()
        let jordan = app.buttons["picker.student.qs-jordan"]
        XCTAssertTrue(jordan.waitForExistence(timeout: 10))
        XCTAssertFalse(app.descendants(matching: .any)["picker.year"].exists, "Quick Life has no year step")
        attachScreenshot("Picker: Quick Life students")
        jordan.tap()

        let start = app.buttons["room.start"]
        XCTAssertTrue(start.waitForExistence(timeout: 10))
        let enabled = NSPredicate(format: "isEnabled == true")
        expectation(for: enabled, evaluatedWith: start)
        waitForExpectations(timeout: 15)
        XCTAssertTrue(app.descendants(matching: .any)["room.game"].label.contains("Quick Life"))
        attachScreenshot("Lobby: host, Quick Life")
    }
}
