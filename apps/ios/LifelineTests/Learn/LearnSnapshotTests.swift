import Foundation
import SwiftUI
import Testing
import UIKit
@testable import Lifeline

/// Screenshots of the Learn screens for review (ADR 0068). Off by default.
/// Run with `TEST_RUNNER_LEARN_SNAPSHOT_DIR=<folder> make ios-test`: PNGs go to that folder, in English and Chinese.
@MainActor
@Suite("Learn snapshots", .serialized, .enabled(if: ProcessInfo.processInfo.environment["LEARN_SNAPSHOT_DIR"] != nil))
struct LearnSnapshotTests {
    let folder = URL(fileURLWithPath: ProcessInfo.processInfo.environment["LEARN_SNAPSHOT_DIR"] ?? NSTemporaryDirectory())

    @Test(arguments: [AppLanguage.en, .zhHans])
    func screens(language: AppLanguage) async throws {
        let saved = UserDefaults.standard.string(forKey: AppLanguage.storageKey)
        AppLanguage.set(language)
        defer {
            if let saved { UserDefaults.standard.set(saved, forKey: AppLanguage.storageKey) } else { UserDefaults.standard.removeObject(forKey: AppLanguage.storageKey) }
        }
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let tag = language.rawValue

        // Play tab with the Learn card.
        try await shoot(PlayView(state: PlayFixturesW7.withEntry), "\(tag)-1-play-card")

        // The path, scrolled to the next lesson.
        let service = MockLearnService(passedCount: 4, bonusCount: 2)
        let path = LearnPathViewModel(service: service, isSampleData: true, language: { language })
        await path.load()
        try await shoot(LearnPathView(state: path.state, actions: path.actions), "\(tag)-2-path")

        // A tap on a locked lesson.
        let order = LearnFixtures.order
        path.select(order[7])
        try await shoot(LearnPathView(state: path.state, actions: path.actions), "\(tag)-3-locked-tap")

        // A lesson: first card, the real number, a question.
        let lesson = LearnLessonViewModel(lessonID: order[4], unitTitle: path.unitTitle(for: order[4]), service: service, isSampleData: true, language: { language })
        await lesson.load()
        try await shoot(LearnLessonView(state: lesson.state), "\(tag)-4-lesson-card")
        while case .card = lesson.step { lesson.next() }
        try await shoot(LearnLessonView(state: lesson.state), "\(tag)-5-lesson-fact")
        lesson.next()
        let quiz = lesson.lesson?.quiz ?? []
        lesson.choose(question: quiz[0].id, choice: quiz[0].choices[0].id)
        try await shoot(LearnLessonView(state: lesson.state), "\(tag)-6-question")

        // Fail first (all wrong), then pass.
        let key = await service.answerKey(order[4])
        for question in quiz {
            lesson.choose(question: question.id, choice: question.choices.first { $0.id != key[question.id] }!.id)
            lesson.next()
        }
        await lesson.submit()
        try await shoot(LearnLessonView(state: lesson.state), "\(tag)-7-result-fail")
        lesson.tryAgain()
        for question in quiz {
            lesson.choose(question: question.id, choice: key[question.id]!)
            lesson.next()
        }
        await lesson.submit()
        try await shoot(LearnLessonView(state: lesson.state), "\(tag)-8-result-pass")
        #expect(lesson.state.result?.passed == true)
    }

    /// Hosts the view in a phone-sized window, waits for layout and the scroll, then writes a PNG.
    private func shoot(_ view: some View, _ name: String) async throws {
        let scene = try #require(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let window = UIWindow(windowScene: scene)
        window.frame = scene.screen.bounds
        let host = UIHostingController(rootView: view.environment(\.appLanguage, AppLanguage.current))
        window.rootViewController = host
        window.makeKeyAndVisible()
        try await Task.sleep(for: .milliseconds(1200))
        let image = UIGraphicsImageRenderer(bounds: window.bounds).image { _ in
            window.drawHierarchy(in: window.bounds, afterScreenUpdates: true)
        }
        window.isHidden = true
        let data = try #require(image.pngData())
        try data.write(to: folder.appendingPathComponent(name + ".png"))
    }
}
