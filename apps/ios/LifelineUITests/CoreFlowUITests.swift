import XCTest

/// Money tab first, then Life: character select -> start year -> AGE -> answer event -> lesson.
/// Uses canned data (`-uiTestingMock`).
final class CoreFlowUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    @MainActor
    func testPresetLifeAgeAndAnswerEvent() {
        let app = XCUIApplication()
        // The full Life game is cut (PENNY_V3_BUILD F); the flag keeps its flow testable.
        app.launchArguments = ["-uiTestingMock", "-showsCutFeatures"]
        app.launch()

        // The app opens on Money. The game is "Play solo" inside the Play tab (ADR 0048).
        let playTab = app.buttons["tab.play"]
        XCTAssertTrue(playTab.waitForExistence(timeout: 10))
        playTab.tap()
        let solo = app.buttons["play.solo"]
        XCTAssertTrue(solo.waitForExistence(timeout: 10))
        solo.tap()

        // "Play yourself" is the first card.
        let playYourself = app.buttons["character.self"]
        XCTAssertTrue(playYourself.waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["character.god"].exists, "God Mode is cut (ADR 0067)")

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
        XCTAssertEqual(ageButton.label, "Age up to 19")
        ageButton.tap()

        // The new event shows as a row on the feed. Tapping it opens the event full screen.
        let pendingEvent = app.descendants(matching: .any)["life.pendingEvent"]
        XCTAssertTrue(pendingEvent.waitForExistence(timeout: 5))
        pendingEvent.tap()

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
    func testMoneyTabOpensOnTheForecast() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock", "-skipOnboarding"]
        app.launch()

        // The forecast card is the first block on the Money tab (ADR 0072, B3.1). The old move card is gone (B4).
        XCTAssertTrue(app.descendants(matching: .any)["money.block.forecast"].firstMatch.waitForExistence(timeout: 15))
        XCTAssertTrue(app.descendants(matching: .any)["forecast.summary"].firstMatch.waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts["nextMove.action"].exists)
        XCTAssertFalse(app.buttons["nextMove.testIt"].exists)
        // Guess my spend has no entry point (F1).
        XCTAssertFalse(app.staticTexts["guess.predicted"].exists)

        // "See the maths" opens the 4 steps.
        let maths = app.buttons["forecast.seeMaths"]
        XCTAssertTrue(maths.waitForExistence(timeout: 5))
        maths.tap()
        XCTAssertTrue(app.descendants(matching: .any)["maths.step.1"].waitForExistence(timeout: 10))
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
        // No "Mock data" tag anywhere (B4).
        XCTAssertFalse(app.descendants(matching: .any)["demoDataBadge"].exists)
    }
}
