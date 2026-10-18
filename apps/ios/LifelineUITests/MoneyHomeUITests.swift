import XCTest

/// Money home on canned data (`-uiTestingMock -skipOnboarding`), ADR 0070: the blocks show top to bottom in order,
/// with no balance tiles. Set `TEST_RUNNER_SCREENSHOT_DIR` to also write each screen as a PNG.
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
    private func walk(language: String?) {
        let prefix = "money-" + (language ?? "en")
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock", "-skipOnboarding"]
        if let language { app.launchArguments += ["-penny.language", language] }
        app.launch()

        let blocks = ["nextMove", "spending", "bills", "subscriptions", "budgetsAndGoals", "accountLine", "guess"]
        let first = app.descendants(matching: .any)["money.block.nextMove"]
        XCTAssertTrue(first.waitForExistence(timeout: 15), "Money home did not load")
        XCTAssertFalse(app.descendants(matching: .any)["money.balance"].exists, "The balance tile is gone (ADR 0070)")
        XCTAssertFalse(app.descendants(matching: .any)["money.netWorth"].exists, "The net worth tile is gone (ADR 0070)")
        shot("\(prefix)-1")

        var lastY = -CGFloat.infinity
        var page = 2
        for id in blocks {
            let element = app.descendants(matching: .any)["money.block.\(id)"].firstMatch
            var swipes = 0
            while !(element.exists && element.isHittable) && swipes < 8 {
                app.swipeUp(velocity: .slow)
                swipes += 1
            }
            XCTAssertTrue(element.exists, "Block \(id) is missing")
            if swipes > 0 {
                shot("\(prefix)-\(page)")
                page += 1
                lastY = -CGFloat.infinity
            }
            // Within one screen, each block sits below the one before.
            XCTAssertGreaterThan(element.frame.minY, lastY, "Block \(id) is out of order")
            lastY = element.frame.minY
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
}
