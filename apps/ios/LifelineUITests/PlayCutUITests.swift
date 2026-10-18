import XCTest

/// PENNY_V3_BUILD F4 and E5: Play = Play with friends + Learn + Join; no Play solo, Challenges or Collection.
/// The You tab shows "Lessons", and tapping it opens Learn.
final class PlayCutUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    /// Saves a screenshot to apps/ios/.build/screens/<name>.png on the host (gitignored) for review.
    @MainActor
    private func snap(_ app: XCUIApplication, _ name: String, file: StaticString = #filePath) {
        let dir = URL(fileURLWithPath: "\(file)").deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent(".build/screens")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        try? app.screenshot().pngRepresentation.write(to: dir.appendingPathComponent("\(name).png"))
    }

    @MainActor
    func testPlayTabShowsFriendsAndLearnOnly() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock"]
        app.launch()

        let playTab = app.buttons["tab.play"]
        XCTAssertTrue(playTab.waitForExistence(timeout: 10))
        playTab.tap()
        XCTAssertTrue(app.buttons["play.friends"].waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["play.learn"].exists)
        XCTAssertTrue(app.buttons["play.join"].exists)
        XCTAssertFalse(app.buttons["play.solo"].exists, "The full Life game is cut")
        XCTAssertFalse(app.buttons["segment.challenges"].exists, "Challenges are cut")
        XCTAssertFalse(app.buttons["segment.collection"].exists, "Collection is cut")
        snap(app, "v3-play")

        // Learn: every lesson is open, so a lesson far down the path opens.
        app.buttons["play.learn"].tap()
        XCTAssertTrue(app.descendants(matching: .any)["learn.progress"].waitForExistence(timeout: 10))
        XCTAssertFalse(app.staticTexts["Pass a lesson to open the next one."].exists)
        snap(app, "v3-learn-path")

        // Open a lesson and walk to "The real number": it has a "Why this matters to you" line.
        let node = app.buttons.matching(NSPredicate(format: "identifier BEGINSWITH 'learn.node.'")).element(boundBy: 2)
        XCTAssertTrue(node.waitForExistence(timeout: 5))
        node.tap()
        let next = app.buttons["learn.lesson.next"]
        XCTAssertTrue(next.waitForExistence(timeout: 10))
        snap(app, "v3-lesson-card")
        let why = app.descendants(matching: .any)["learn.lesson.why.0"]
        for _ in 0..<5 where !why.exists {
            next.tap()
            _ = why.waitForExistence(timeout: 1)
        }
        XCTAssertTrue(why.exists, "The real number shows why it matters")
        snap(app, "v3-lesson-fact")
    }

    @MainActor
    func testYouTabShowsLessonsAndNoCutRows() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock"]
        app.launch()

        let youTab = app.buttons["tab.you"]
        XCTAssertTrue(youTab.waitForExistence(timeout: 10))
        youTab.tap()
        let lessons = app.buttons["you.lessons"]
        XCTAssertTrue(lessons.waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["you.spendAccuracy"].exists, "Guess my spend is cut")
        XCTAssertFalse(app.buttons["you.evaluation"].exists)
        XCTAssertFalse(app.staticTexts["Concepts learned"].exists)
        snap(app, "v3-you")
        app.swipeUp()
        snap(app, "v3-you-2")
        app.swipeUp()
        snap(app, "v3-you-3")
        app.swipeDown(); app.swipeDown()
        lessons.tap()
        XCTAssertTrue(app.descendants(matching: .any)["learn.progress"].waitForExistence(timeout: 10))
    }
}
