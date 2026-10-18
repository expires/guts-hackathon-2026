import XCTest

/// Penny tab on canned data (`-uiTestingMock -skipOnboarding`), PENNY_V3_BUILD D1 to D3. W7.
/// Set `TEST_RUNNER_SCREENSHOT_DIR` to also write each screen as a PNG (the shots are attached to the result too).
final class PennyUITests: XCTestCase {
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

    private func elements(_ app: XCUIApplication, prefix: String) -> [XCUIElement] {
        app.descendants(matching: .any)
            .matching(NSPredicate(format: "identifier BEGINSWITH %@", prefix))
            .allElementsBoundByIndex
    }

    @MainActor
    func testOneAnswerOneLabelThenPastChatsAndNewChat() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock", "-skipOnboarding", "-penny.language", "en"]
        app.launch()

        let tab = app.buttons["tab.penny"]
        XCTAssertTrue(tab.waitForExistence(timeout: 15))
        tab.tap()
        XCTAssertTrue(app.descendants(matching: .any)["penny.intro"].waitForExistence(timeout: 5))
        // Earlier chats are no longer listed inside the chat (D3).
        XCTAssertFalse(app.staticTexts["Earlier chats"].exists)
        XCTAssertTrue(app.buttons["penny.pastChats"].exists)

        let chip = app.buttons.matching(identifier: "penny.chip").firstMatch
        XCTAssertTrue(chip.waitForExistence(timeout: 5))
        chip.tap()

        // Wait for the final answer: the mode label shows only when the answer is complete.
        let label = app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH 'penny.mode.'")).firstMatch
        XCTAssertTrue(label.waitForExistence(timeout: 20))
        // Let the replace animation finish, then check the screen.
        let typing = app.descendants(matching: .any)["penny.typing"]
        let gone = expectation(for: NSPredicate(format: "exists == false"), evaluatedWith: typing)
        wait(for: [gone], timeout: 10)
        sleep(1)
        shot("penny-1-one-answer")

        // D1: one mode label and one set of bubbles for the one answer.
        XCTAssertEqual(elements(app, prefix: "penny.mode.").count, 1, "Two mode labels overlap")
        let bubbles = elements(app, prefix: "penny.bubble.").map(\.identifier)
        XCTAssertFalse(bubbles.isEmpty)
        XCTAssertEqual(bubbles.count, Set(bubbles).count, "A bubble shows twice")
        XCTAssertLessThanOrEqual(bubbles.count, 3, "At most 3 bubbles per answer (D6)")
        for id in Set(bubbles) {
            let frames = elements(app, prefix: id).filter { $0.identifier == id }.map(\.frame)
            XCTAssertEqual(frames.count, 1, "Bubble \(id) is on screen twice")
        }

        // D3: Past chats on their own screen.
        app.buttons["penny.pastChats"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["penny.pastChats"].waitForExistence(timeout: 5))
        sleep(1)
        shot("penny-2-past-chats")
        app.buttons["penny.pastChats.close"].tap()

        // D2: New chat clears the chat.
        let newChat = app.buttons["penny.newChat"]
        XCTAssertTrue(newChat.waitForExistence(timeout: 5))
        newChat.tap()
        XCTAssertTrue(app.descendants(matching: .any)["penny.intro"].waitForExistence(timeout: 5))
        XCTAssertEqual(elements(app, prefix: "penny.bubble.").count, 0)
    }
}
