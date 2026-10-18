import XCTest

/// PENNY_V3_BUILD B4, G4, G5: no "Mock data" or "Sample data" text on Money, Penny, Play or You.
final class NoMockTextUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = true
    }

    @MainActor
    func testNoMockOrSampleDataTextOnAnyTab() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock"]
        app.launch()
        let predicate = NSPredicate(format: "label CONTAINS[c] 'mock data' OR label CONTAINS[c] 'sample data' OR value CONTAINS[c] 'mock data' OR value CONTAINS[c] 'sample data'")
        for tab in ["money", "penny", "play", "you"] {
            let button = app.buttons["tab.\(tab)"]
            XCTAssertTrue(button.waitForExistence(timeout: 10), "No \(tab) tab")
            button.tap()
            // Let the tab load, then check the screen and one screen further down.
            _ = app.staticTexts.firstMatch.waitForExistence(timeout: 5)
            sleep(2)
            for pass in 0..<3 {
                let hits = app.descendants(matching: .any).matching(predicate)
                XCTAssertEqual(hits.count, 0, "\(tab) tab, scroll \(pass): \(hits.allElementsBoundByIndex.map(\.label))")
                if tab == "penny" { break }
                app.swipeUp()
            }
        }
    }
}
