import XCTest

/// Money home on canned data (`-uiTestingMock -skipOnboarding`), ADR 0072: the blocks show top to bottom in order,
/// then The maths, the detailed breakdown, All spending and one category open. No "Mock data" or "Sample data" text.
/// Set `SCREENSHOT_DIR` (as `TEST_RUNNER_SCREENSHOT_DIR`) to also write each screen as a PNG.
final class MoneyHomeUITests: XCTestCase {
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

    @MainActor
    private func launch(language: String? = nil, extra: [String] = []) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock", "-skipOnboarding"] + extra
        if let language { app.launchArguments += ["-penny.language", language] }
        app.launch()
        return app
    }

    @MainActor
    private func element(_ app: XCUIApplication, _ id: String) -> XCUIElement {
        app.descendants(matching: .any)[id].firstMatch
    }

    @MainActor
    private func scrollTo(_ app: XCUIApplication, _ id: String, up: Bool = false) -> XCUIElement {
        let target = element(app, id)
        var swipes = 0
        // The floating tab bar covers the bottom of the screen: keep the target well above it before tapping.
        let limit = app.frame.height - 170
        func visible() -> Bool { target.exists && target.isHittable && target.frame.maxY < limit && target.frame.minY > 60 }
        while !visible() && swipes < 10 {
            if target.exists, target.frame.minY <= 60 {
                app.swipeDown(velocity: .slow)
            } else if target.exists, target.frame.maxY >= limit {
                app.swipeUp(velocity: .slow)
            } else {
                up ? app.swipeDown(velocity: .slow) : app.swipeUp(velocity: .slow)
            }
            swipes += 1
        }
        return target
    }

    @MainActor
    private func assertNoDataTags(_ app: XCUIApplication, _ screen: String) {
        for tag in ["Mock data", "Sample data"] {
            let found = app.staticTexts.containing(NSPredicate(format: "label CONTAINS[c] %@", tag)).count
            XCTAssertEqual(found, 0, "\(screen) shows \"\(tag)\" (B4)")
        }
    }

    @MainActor
    private func walk(language: String?) {
        let prefix = "money-" + (language ?? "en")
        let app = launch(language: language)

        let first = element(app, "money.block.forecast")
        XCTAssertTrue(first.waitForExistence(timeout: 15), "Money home did not load")
        XCTAssertTrue(element(app, "forecast.seeMaths").waitForExistence(timeout: 15), "The forecast card did not load")
        XCTAssertFalse(element(app, "money.balance").exists, "The balance tile is gone (B4)")
        XCTAssertFalse(element(app, "guess.card").exists, "Guess my spend is gone (B4)")
        assertNoDataTags(app, "Money home")
        shot("\(prefix)-1")

        var lastY = -CGFloat.infinity
        var page = 2
        for id in ["forecast", "spending", "due", "help", "accountLine"] {
            let block = element(app, "money.block.\(id)")
            var swipes = 0
            while !(block.exists && block.isHittable) && swipes < 8 {
                app.swipeUp(velocity: .slow)
                swipes += 1
            }
            XCTAssertTrue(block.exists, "Block \(id) is missing")
            if swipes > 0 {
                shot("\(prefix)-\(page)")
                page += 1
                lastY = -CGFloat.infinity
            }
            XCTAssertGreaterThan(block.frame.minY, lastY, "Block \(id) is out of order")
            lastY = block.frame.minY
        }
    }

    @MainActor
    func testMoneyHomeBlocksInOrderEnglish() {
        walk(language: nil)
    }

    @MainActor
    func testMoneyHomeBlocksInOrderChinese() {
        walk(language: "zh-Hans")
    }

    /// The maths, the buffer buttons, "Ask Penny what if", the detailed breakdown.
    @MainActor
    func testTheMathsAndDetailedBreakdown() {
        let app = launch()
        let maths = element(app, "forecast.seeMaths")
        XCTAssertTrue(maths.waitForExistence(timeout: 15))
        maths.tap()
        XCTAssertTrue(element(app, "maths.intro").waitForExistence(timeout: 10), "The maths did not open")
        assertNoDataTags(app, "The maths")
        shot("maths-1")
        let buffer = element(app, "maths.buffer.15")
        XCTAssertTrue(buffer.waitForExistence(timeout: 5))
        buffer.tap()
        XCTAssertTrue(element(app, "maths.buffer.15").waitForExistence(timeout: 5))
        buffer.tap() // no-op when already selected
        element(app, "maths.buffer.10").tap()
        XCTAssertTrue(scrollTo(app, "maths.whatIf").exists, "Ask Penny 'what if...' replaces the 2022 button")
        XCTAssertFalse(element(app, "maths.stress").exists)
        shot("maths-2")
        _ = scrollTo(app, "maths.detail", up: true).tap()
        XCTAssertTrue(element(app, "breakdown.section.1").waitForExistence(timeout: 10), "The breakdown did not open")
        assertNoDataTags(app, "Detailed breakdown")
        shot("breakdown-1")
        for page in 2...4 {
            app.swipeUp(velocity: .slow)
            app.swipeUp(velocity: .slow)
            shot("breakdown-\(page)")
        }
    }

    /// All spending with its month switch, then one category.
    @MainActor
    func testAllSpendingAndCategory() {
        let app = launch()
        XCTAssertTrue(element(app, "forecast.seeMaths").waitForExistence(timeout: 15))
        let seeAll = scrollTo(app, "money.seeAllSpending")
        XCTAssertTrue(seeAll.exists)
        seeAll.tap()
        let month = element(app, "spending.month")
        XCTAssertTrue(month.waitForExistence(timeout: 10), "All spending did not open")
        assertNoDataTags(app, "All spending")
        shot("spending-1")
        let thisMonth = month.label
        element(app, "spending.previous").tap()
        let moved = NSPredicate(format: "label != %@", thisMonth)
        expectation(for: moved, evaluatedWith: month)
        waitForExpectations(timeout: 10)
        shot("spending-2")
        element(app, "spending.next").tap()
        let category = app.descendants(matching: .any).matching(NSPredicate(format: "identifier BEGINSWITH 'spending.category.'")).firstMatch
        XCTAssertTrue(category.waitForExistence(timeout: 10))
        category.tap()
        XCTAssertTrue(element(app, "category.total").waitForExistence(timeout: 10), "The category did not open")
        assertNoDataTags(app, "Category")
        shot("category-1")
        app.swipeUp(velocity: .slow)
        shot("category-2")
    }

    /// Running short (canvas 2).
    @MainActor
    func testRunningShortCard() {
        let app = launch(extra: ["-mockForecastShort"])
        let summary = element(app, "forecast.summary")
        XCTAssertTrue(summary.waitForExistence(timeout: 15), "The forecast card did not load")
        XCTAssertTrue(summary.label.contains("Running short"), "Expected the running short card, got: \(summary.label)")
        shot("money-short-1")
    }
}
