import XCTest

/// "Play as yourself": Play tab card, who you are playing as, connect step, profile stats; and You > Connect your
/// money. Canned data (`-uiTestingMock -skipOnboarding`). Set `TEST_RUNNER_SCREENSHOT_DIR` to also write PNGs.
final class ProfileFlowUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    private func shot(_ name: String) {
        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
        if let dir = ProcessInfo.processInfo.environment["SCREENSHOT_DIR"], !dir.isEmpty {
            let url = URL(fileURLWithPath: dir).appendingPathComponent(name + ".png")
            try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try? screenshot.pngRepresentation.write(to: url)
        }
    }

    private func any(_ app: XCUIApplication, _ id: String) -> XCUIElement {
        app.descendants(matching: .any)[id]
    }

    private func launch(profile: String? = nil) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock", "-skipOnboarding"]
        if let profile { app.launchArguments += ["-mockProfile", profile] }
        app.launch()
        return app
    }

    @MainActor
    func testPlayAsYourselfCardPickerConnectAndStats() {
        let app = launch(profile: "nothing")
        let play = app.buttons["tab.play"]
        XCTAssertTrue(play.waitForExistence(timeout: 15))
        play.tap()
        let card = any(app, "play.yourself")
        XCTAssertTrue(card.waitForExistence(timeout: 10))
        // The card sits above Play with friends.
        XCTAssertLessThan(card.frame.minY, any(app, "play.friends").frame.minY)
        shot("pay-01-play-tab")
        card.tap()

        XCTAssertTrue(any(app, "picker.card.you").waitForExistence(timeout: 10))
        shot("pay-02-picker")
        any(app, "picker.card.you").tap()

        XCTAssertTrue(any(app, "connections.row.trading212").waitForExistence(timeout: 10))
        for kind in ["monzo", "trading212", "statement", "manual"] { XCTAssertTrue(any(app, "connections.row.\(kind)").exists) }
        shot("pay-03-connect")
        app.buttons["connections.connect.trading212"].tap()
        let key = app.textFields["trading212.key"]
        XCTAssertTrue(key.waitForExistence(timeout: 5))
        key.tap()
        key.typeText("abc")
        let secret = app.secureTextFields["trading212.secret"]
        secret.tap()
        secret.typeText("def")
        shot("pay-04-trading212-sheet")
        app.buttons["trading212.connect"].tap()
        XCTAssertTrue(any(app, "connections.notice").waitForExistence(timeout: 5))
        shot("pay-05-connect-after")
        app.buttons["connections.continue"].tap()

        XCTAssertTrue(any(app, "profile.section.investments").waitForExistence(timeout: 10))
        XCTAssertTrue(any(app, "profile.jump.habits").exists)
        shot("pay-06-stats-t212-only")
        app.swipeUp()
        shot("pay-07-stats-t212-only-bottom")
    }

    @MainActor
    func testFullStatsAndSample() {
        let app = launch(profile: "monzoAndT212")
        app.buttons["tab.play"].tap()
        any(app, "play.yourself").tap()
        XCTAssertTrue(any(app, "picker.card.you").waitForExistence(timeout: 10))
        shot("pay-08-picker-you-active")
        any(app, "picker.card.you").tap()
        app.buttons["connections.continue"].tap()
        XCTAssertTrue(any(app, "profile.section.habits").waitForExistence(timeout: 10))
        shot("pay-09-stats-full")
        app.swipeUp()
        shot("pay-10-stats-full-2")
        app.swipeUp()
        shot("pay-11-stats-full-3")
    }

    @MainActor
    func testSampleStudentGoesStraightToStats() {
        let app = launch(profile: "nothing")
        app.buttons["tab.play"].tap()
        any(app, "play.yourself").tap()
        let first = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'picker.card.' AND NOT identifier ENDSWITH '.you'")).firstMatch
        XCTAssertTrue(first.waitForExistence(timeout: 10))
        first.tap()
        XCTAssertTrue(any(app, "profile.section.habits").waitForExistence(timeout: 10))
        XCTAssertFalse(any(app, "profile.jump.habits").exists)
        shot("pay-12-stats-sample")
    }

    @MainActor
    func testYouTabConnectionsEditorHasNoStudentPicker() {
        let app = launch(profile: "monzoAndT212")
        app.buttons["tab.you"].tap()
        let row = any(app, "you.connectMoney")
        XCTAssertTrue(row.waitForExistence(timeout: 10))
        row.tap()
        XCTAssertTrue(any(app, "connections.row.monzo").waitForExistence(timeout: 10))
        XCTAssertFalse(any(app, "connections.continue").exists)
        XCTAssertFalse(any(app, "picker.card.you").exists)
        XCTAssertEqual(any(app, "connections.status.monzo").label, "Connected")
        shot("pay-you-connections")
        app.buttons["connections.disconnect.trading212"].tap()
        shot("pay-you-connections-confirm")
    }
}
