import XCTest

/// The app is stripped to real money (`AppFeatures.game == false`): Money and You tabs.
/// The Life game test is skipped while the game is hidden. Uses canned data (`-uiTestingMock`).
final class CoreFlowUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    @MainActor
    func testPresetLifeAgeAndAnswerEvent() throws {
        throw XCTSkip("The Life game is hidden (AppFeatures.game = false). Re-enable with the flag.")
        // swiftlint:disable:next unreachable_code
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock"]
        app.launch()

        // The app opens on Money (ADR 0016). The game is in the Life tab.
        let lifeTab = app.buttons["tab.life"]
        XCTAssertTrue(lifeTab.waitForExistence(timeout: 10))
        lifeTab.tap()

        // "Play yourself" is the first card.
        let playYourself = app.buttons["character.self"]
        XCTAssertTrue(playYourself.waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["character.god"].exists)

        let amira = app.buttons["character.preset.nurse-leeds"]
        XCTAssertTrue(amira.waitForExistence(timeout: 5))
        XCTAssertLessThan(playYourself.frame.minY, amira.frame.minY, "Play yourself must come first")
        amira.tap()

        let start = app.buttons["startYear.start"]
        XCTAssertTrue(start.waitForExistence(timeout: 5))
        start.tap()

        let ageButton = app.buttons["life.ageButton"]
        XCTAssertTrue(ageButton.waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["life.age"].waitForExistence(timeout: 2))
        XCTAssertEqual(app.staticTexts["life.age"].label, "Age 18")
        ageButton.tap()

        let choice = app.buttons["event.choice.move"]
        XCTAssertTrue(choice.waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["event.title"].exists)
        XCTAssertTrue(app.descendants(matching: .any)["sourceChip.ons"].exists)
        choice.tap()

        // The choice unlocks a concept, so the lesson opens. Answer the quiz and close it.
        let close = app.buttons["lesson.close"]
        XCTAssertTrue(close.waitForExistence(timeout: 5))
        app.buttons["lesson.option.1"].tap()
        XCTAssertTrue(app.staticTexts["lesson.feedback"].waitForExistence(timeout: 2))
        close.tap()

        XCTAssertTrue(app.descendants(matching: .any)["life.outcome"].waitForExistence(timeout: 5))
        XCTAssertFalse(choice.exists)
        XCTAssertEqual(app.staticTexts["life.age"].label, "Age 19")
        XCTAssertTrue(ageButton.isEnabled)
    }

    @MainActor
    func testMoneyTabOpensOnNextMove() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock"]
        app.launch()

        // The Next Move card is the first element on the Money tab (ADR 0018).
        let action = app.staticTexts["nextMove.action"]
        XCTAssertTrue(action.waitForExistence(timeout: 10))
        // The expected move comes from the recorded engine output, never from a hard-coded decision.
        XCTAssertEqual(action.label, Self.recordedTopAction())
        XCTAssertTrue(app.staticTexts["nextMove.headline"].exists)

        // Guess my spend hides the prediction until the guess (ADR 0017).
        XCTAssertFalse(app.staticTexts["guess.predicted"].exists)

        // Do this adds the move to the plan.
        let doThis = app.buttons["nextMove.doThis"]
        XCTAssertTrue(doThis.waitForExistence(timeout: 5))
        doThis.tap()
        XCTAssertTrue(app.descendants(matching: .any)["nextMove.planMessage"].waitForExistence(timeout: 5))

        // Test it launches the hidden game simulation, so the button must not be there.
        XCTAssertFalse(app.buttons["nextMove.testIt"].exists)
        XCTAssertFalse(app.buttons["tab.life"].exists)
        XCTAssertFalse(app.buttons["tab.play"].exists)
        XCTAssertTrue(app.buttons["tab.you"].exists)

        // Why? shows the 3 evidence points.
        let why = app.buttons["nextMove.why"]
        XCTAssertTrue(why.waitForExistence(timeout: 5))
        why.tap()
        XCTAssertTrue(app.descendants(matching: .any)["why.evidence.2"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["why.testIt"].exists)
        XCTAssertFalse(app.buttons["why.openLesson"].exists)
        app.buttons["why.close"].tap()
    }

    @MainActor
    func testInsightsChartExplainerOpens() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock"]
        app.launch()

        let insights = app.buttons["money.insights"]
        XCTAssertTrue(insights.waitForExistence(timeout: 10))
        for _ in 0..<6 where !insights.isHittable { app.swipeUp() }
        sleep(1)
        insights.coordinate(withNormalizedOffset: CGVector(dx: 0.3, dy: 0.15)).tap()
        XCTAssertTrue(app.buttons["insights.back"].waitForExistence(timeout: 10), "Insights did not open")

        // The card's own identifier ("insights.months") wins over the button's inside it.
        let info = app.buttons["insights.months"]
        XCTAssertTrue(info.waitForExistence(timeout: 10), app.debugDescription)
        XCTAssertEqual(info.label, "About this chart")
        info.tap()
        XCTAssertTrue(app.staticTexts["What this shows"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts["How to read it"].exists)
        XCTAssertTrue(app.staticTexts["What it means for you"].exists)
        app.buttons["chart.explainer.close"].tap()
    }

    @MainActor
    func testYouTabHasNoGameRows() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock"]
        app.launch()
        app.buttons["tab.you"].tap()
        XCTAssertTrue(app.buttons["you.plan"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["you.store"].exists)
        XCTAssertFalse(app.buttons["you.evaluation"].exists)
        XCTAssertFalse(app.buttons["you.spendAccuracy"].exists)
    }

    @MainActor
    func testFriendsTabOpensAddAFriend() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock"]
        app.launch()
        let tab = app.buttons["tab.friends"]
        XCTAssertTrue(tab.waitForExistence(timeout: 10))
        tab.tap()
        XCTAssertTrue(app.staticTexts["friends.intro"].waitForExistence(timeout: 10))
        let add = app.buttons["friends.add"]
        XCTAssertTrue(add.waitForExistence(timeout: 10))
        add.tap()
        let code = app.staticTexts["addFriend.code"]
        XCTAssertTrue(code.waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["addFriend.copy"].exists)
        XCTAssertTrue(app.buttons["addFriend.rotate"].exists)
        XCTAssertTrue(app.textFields["addFriend.input"].exists)
        app.buttons["addFriend.close"].tap()
        XCTAssertTrue(add.waitForExistence(timeout: 5))
    }

    /// `top.action` from `Lifeline/Preview/Recorded/getNextMove.json` (the file the app's mock client serves).
    /// The simulator test runner can read the source tree on the host Mac.
    static func recordedTopAction(file: StaticString = #filePath) -> String {
        let url = URL(fileURLWithPath: "\(file)")
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("Lifeline/Preview/Recorded/getNextMove.json")
        guard let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let top = json["top"] as? [String: Any],
              let action = top["action"] as? String else {
            XCTFail("Cannot read top.action from \(url.path)")
            return ""
        }
        return action
    }

    @MainActor
    func testPlaygroundGalleryOpens() {
        let app = XCUIApplication()
        app.launchArguments = ["-playground"]
        app.launch()
        let entry = app.descendants(matching: .any)["gallery.select.ready"]
        XCTAssertTrue(entry.waitForExistence(timeout: 10))
        entry.tap()
        XCTAssertTrue(app.buttons["character.self"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.descendants(matching: .any)["demoDataBadge"].exists)
    }
}
