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
}
