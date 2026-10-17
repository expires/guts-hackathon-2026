import XCTest

/// Onboarding gate on canned data (`-uiTestingMock -onboarding`): welcome, demo sign-in, connect your money.
final class OnboardingUITests: XCTestCase {
    override func setUp() {
        continueAfterFailure = false
    }

    @MainActor
    func testWelcomeToConnectAndManualChecks() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock", "-onboarding"]
        app.launch()

        let next = app.buttons["onboarding.next"]
        XCTAssertTrue(next.waitForExistence(timeout: 10))
        next.tap()
        next.tap()
        next.tap()

        // The simulator has no Sign in with Apple capability: demo sign-in only.
        let demo = app.buttons["onboarding.demo"]
        XCTAssertTrue(demo.waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["onboarding.apple"].exists)
        demo.tap()

        // Bank connections are cut (ADR 0046): statement upload and manual entry only.
        XCTAssertTrue(app.buttons["onboarding.option.statement"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["onboarding.option.monzo"].exists)
        XCTAssertFalse(app.buttons["onboarding.option.trading212"].exists)

        app.buttons["onboarding.option.manual"].tap()
        let save = app.buttons["onboarding.manual.save"]
        XCTAssertTrue(save.waitForExistence(timeout: 5))
        save.tap()
        XCTAssertTrue(app.descendants(matching: .any)["onboarding.manual.problems"].waitForExistence(timeout: 5))
    }
}
