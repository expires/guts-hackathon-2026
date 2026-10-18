import XCTest

/// Onboarding gate on canned data (`-uiTestingMock -onboarding`), ADR 0069 order:
/// Welcome, Problem, Language, What you can do, Try Penny, Pick your student, Building their profile,
/// Their profile, How Penny decides, Their Next Move, Start.
/// Set `TEST_RUNNER_SCREENSHOT_DIR` to also write each screen as a PNG (the shots are attached to the result too).
final class OnboardingUITests: XCTestCase {
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

    private func any(_ app: XCUIApplication, _ identifier: String) -> XCUIElement {
        app.descendants(matching: .any)[identifier]
    }

    /// Walks the whole flow. `language` nil confirms English on the language screen; otherwise the app was
    /// launched in that language and Skip keeps it (nothing is saved, so other tests stay in English).
    @MainActor
    private func walkFlow(language: String?) {
        let prefix = language ?? "en"
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock", "-onboarding", "-onboardingRecorded"]
        if let language { app.launchArguments += ["-penny.language", language] }
        app.launch()

        // Welcome (no Back: it is the first screen).
        let next = app.buttons["onboarding.next"]
        XCTAssertTrue(next.waitForExistence(timeout: 10))
        XCTAssertFalse(app.buttons["onboarding.back"].exists)
        for id in ["who", "what", "get"] {
            XCTAssertTrue(any(app, "onboarding.welcome.\(id)").exists, id)
        }
        shot("\(prefix)-01-welcome")
        next.tap()

        // Problem, with Back to Welcome.
        XCTAssertTrue(any(app, "onboarding.problem.title").waitForExistence(timeout: 5))
        XCTAssertTrue(any(app, "onboarding.problem.money").exists)
        XCTAssertTrue(any(app, "onboarding.problem.data").exists)
        shot("\(prefix)-02-problem")
        app.buttons["onboarding.back"].tap()
        XCTAssertTrue(any(app, "onboarding.welcome.title").waitForExistence(timeout: 5))
        app.buttons["onboarding.next"].tap()
        XCTAssertTrue(any(app, "onboarding.problem.title").waitForExistence(timeout: 5))
        app.buttons["onboarding.next"].tap()

        // Language: live on tap, then Confirm (English) or Skip (keeps the launch language).
        let french = app.buttons["onboarding.language.fr"]
        XCTAssertTrue(french.waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["onboarding.back"].exists)
        XCTAssertTrue(app.buttons["onboarding.skip"].exists)
        if language == nil {
            french.tap()
            XCTAssertEqual(app.buttons["onboarding.language.confirm"].label, "Confirmer")
            app.buttons["onboarding.language.en"].tap()
            shot("\(prefix)-03-language")
            app.buttons["onboarding.language.confirm"].tap()
        } else {
            shot("\(prefix)-03-language")
            app.buttons["onboarding.skip"].tap()
        }

        // What you can do: 5 explainer rows, none of them buttons.
        XCTAssertTrue(any(app, "onboarding.feature.allMoney").waitForExistence(timeout: 5))
        for id in ["allMoney", "weekly", "maths", "penny", "friends"] {
            XCTAssertTrue(any(app, "onboarding.feature.\(id)").exists, id)
            XCTAssertFalse(app.buttons["onboarding.feature.\(id)"].exists, "\(id) must not look tappable")
        }
        XCTAssertFalse(app.buttons["onboarding.skip"].exists)
        shot("\(prefix)-04-what-you-can-do")
        app.buttons["onboarding.next"].tap()

        // Try Penny: Back and Skip.
        let pennySkip = app.buttons["onboarding.penny.skip"]
        XCTAssertTrue(pennySkip.waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["onboarding.back"].exists)
        shot("\(prefix)-05-try-penny")
        pennySkip.tap()

        // Pick your student: student cards, then Monzo, Trading 212, upload and manual entry.
        let student = app.buttons["onboarding.sample.scottish"]
        XCTAssertTrue(student.waitForExistence(timeout: 10))
        XCTAssertTrue(app.buttons["onboarding.option.statement"].exists)
        XCTAssertTrue(app.buttons["onboarding.option.monzo"].exists)
        // No "Mock data" tag (B4); the honesty line sits under the list.
        XCTAssertFalse(any(app, "demoDataBadge").exists)
        shot("\(prefix)-06-pick-your-student")
        app.swipeUp()
        XCTAssertTrue(any(app, "onboarding.honesty").waitForExistence(timeout: 5))
        shot("\(prefix)-06b-pick-your-student-honesty")
        app.swipeDown()
        app.swipeDown()
        student.tap()

        // Building their profile: no auto-jump, "View profile" when every stage ended.
        let viewProfile = app.buttons["onboarding.viewProfile"]
        XCTAssertTrue(any(app, "onboarding.stage.read").waitForExistence(timeout: 5))
        shot("\(prefix)-07-building")
        XCTAssertTrue(viewProfile.waitForExistence(timeout: 20))
        sleep(1)
        XCTAssertTrue(any(app, "onboarding.stage.profile").exists)
        shot("\(prefix)-08-building-done")
        viewProfile.tap()

        // Their profile.
        XCTAssertTrue(any(app, "onboarding.profile.name").waitForExistence(timeout: 5))
        XCTAssertTrue(any(app, "onboarding.habit.savings_rate").exists)
        XCTAssertTrue(any(app, "onboarding.profile.period").exists)
        XCTAssertFalse(any(app, "demoDataBadge").exists)
        shot("\(prefix)-09-profile")
        app.swipeUp()
        shot("\(prefix)-09b-profile-bills")
        app.swipeUp()
        shot("\(prefix)-10-profile-more")
        // "Penny noticed": tap shows the evidence.
        let noticed = app.buttons["onboarding.noticed.subscriptions_total"]
        XCTAssertTrue(noticed.waitForExistence(timeout: 5))
        noticed.tap()
        app.swipeUp()
        shot("\(prefix)-11-profile-evidence")
        app.buttons["onboarding.next"].tap()

        // How Penny decides: the 4 forecast steps with sources, then the result. Back and Skip.
        XCTAssertTrue(any(app, "onboarding.decides.title").waitForExistence(timeout: 5))
        XCTAssertTrue(app.buttons["onboarding.skip"].exists)
        for number in 1...4 {
            XCTAssertTrue(any(app, "onboarding.decides.step.\(number)").exists, "step \(number)")
        }
        shot("\(prefix)-12-how-penny-decides")
        app.swipeUp()
        XCTAssertTrue(any(app, "onboarding.decides.result").waitForExistence(timeout: 5))
        shot("\(prefix)-12b-how-penny-decides-result")
        app.buttons["onboarding.next"].tap()

        // Their Next Move: the forecast card. "See the maths" goes back to How Penny decides.
        XCTAssertTrue(any(app, "forecast.card").waitForExistence(timeout: 5))
        XCTAssertTrue(any(app, "forecast.headline").exists || any(app, "forecast.summary").exists)
        shot("\(prefix)-13-next-move")
        app.buttons["forecast.seeMaths"].tap()
        XCTAssertTrue(any(app, "onboarding.decides.title").waitForExistence(timeout: 5))
        app.buttons["onboarding.next"].tap()
        XCTAssertTrue(app.buttons["onboarding.back"].waitForExistence(timeout: 5))
        app.buttons["onboarding.back"].tap()
        XCTAssertTrue(any(app, "onboarding.decides.title").waitForExistence(timeout: 5))
        app.buttons["onboarding.next"].tap()
        XCTAssertTrue(app.buttons["onboarding.finish"].waitForExistence(timeout: 5))
    }

    @MainActor
    func testFullFlowInEnglish() {
        walkFlow(language: nil)
    }

    @MainActor
    func testFullFlowInChinese() {
        walkFlow(language: "zh-Hans")
    }

    @MainActor
    func testManualEntryChecks() {
        let app = XCUIApplication()
        app.launchArguments = ["-uiTestingMock", "-onboarding", "-penny.language", "en"]
        app.launch()
        let next = app.buttons["onboarding.next"]
        XCTAssertTrue(next.waitForExistence(timeout: 10))
        next.tap()
        XCTAssertTrue(app.buttons["onboarding.next"].waitForExistence(timeout: 5))
        app.buttons["onboarding.next"].tap()
        XCTAssertTrue(app.buttons["onboarding.skip"].waitForExistence(timeout: 5))
        app.buttons["onboarding.skip"].tap()
        XCTAssertTrue(app.buttons["onboarding.next"].waitForExistence(timeout: 5))
        app.buttons["onboarding.next"].tap()
        let pennySkip = app.buttons["onboarding.penny.skip"]
        XCTAssertTrue(pennySkip.waitForExistence(timeout: 5))
        pennySkip.tap()
        let manual = app.buttons["onboarding.option.manual"]
        XCTAssertTrue(manual.waitForExistence(timeout: 5))
        manual.tap()
        let save = app.buttons["onboarding.manual.save"]
        XCTAssertTrue(save.waitForExistence(timeout: 5))
        // Manual entry: Back, no Skip.
        XCTAssertTrue(app.buttons["onboarding.back"].exists)
        XCTAssertFalse(app.buttons["onboarding.skip"].exists)
        save.tap()
        XCTAssertTrue(app.descendants(matching: .any)["onboarding.manual.problems"].waitForExistence(timeout: 5))
    }
}
