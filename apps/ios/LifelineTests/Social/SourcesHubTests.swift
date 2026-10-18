import Foundation
import SwiftUI
import Testing
import UIKit
@testable import Lifeline

/// ADR 0073: the sources hub ("Where Penny's data comes from"), its entry points and the Try Penny chips.
@MainActor
@Suite("Sources hub (ADR 0073)")
struct SourcesHubTests {
    let now = SourcesHubFixtures.now

    // MARK: Mapping

    @Test func mockHubMapsToOneCardPerStudentSource() {
        let state = SourcesHubFixtures.ready
        #expect(state.phase == .ready)
        #expect(state.summary == "Penny uses your statement plus 7 live UK sources. Here is what each one does.")
        #expect(state.liveCount == 7)
        #expect(state.cards.map(\.id) == ["statement", "facts", "boe", "ons", "nomis", "octopus", "frankfurter", "boe-mpc"])
    }

    @Test func cardShowsStatusTimeGivesAndScreens() throws {
        let boe = try #require(SourcesHubFixtures.ready.card(id: "boe"))
        #expect(boe.name == "Bank of England")
        #expect(boe.status == .live)
        #expect(boe.statusText == "Live")
        #expect(boe.updatedText == "Updated 5 min ago")
        #expect(boe.gives == "Interest rates for saving and borrowing.")
        #expect(boe.usedInText == "Used in: One thing that helps, The maths")
        #expect(boe.latest.map(\.label) == ["Easy-access savings rate", "Bank Rate"])
        #expect(boe.latest.first?.value == "2.06%")
        #expect(boe.latest.first?.asOfText == "As of Sep 2026")
        #expect(boe.url?.absoluteString == "https://www.bankofengland.co.uk/boeapps/database")
        #expect(boe.accessibilitySummary.hasPrefix("Bank of England. Live. Updated 5 min ago."))
    }

    @Test func officialFactsAndSavedCopiesSayWhatTheyAre() throws {
        let state = SourcesHubFixtures.ready
        #expect(try #require(state.card(id: "facts")).statusText == "Checked figures")
        #expect(try #require(state.card(id: "nomis")).statusText == "Saved copy")
        #expect(try #require(state.card(id: "nomis")).updatedText == "Updated 3 days ago")
        #expect(try #require(state.card(id: "statement")).url == nil)
    }

    @Test func homeownerAndUnknownSourcesAreHidden() {
        var hub = SourcesHubMock.hub(now: now)
        hub.sources += [
            HubSource(id: "landregistry", name: "HM Land Registry", kind: .live, status: .live, gives: "House prices.", usedIn: ["Home"]),
            HubSource(id: "epc", name: "EPC register", kind: .officialFacts, status: .cached, gives: "Energy ratings.", usedIn: []),
            HubSource(id: "newfeed", name: "Some new feed", kind: .live, status: .live, gives: "Something.", usedIn: []),
        ]
        let ids = SourcesHubMapping.state(hub, now: now).cards.map(\.id)
        #expect(!ids.contains("landregistry"))
        #expect(!ids.contains("epc"))
        #expect(!ids.contains("newfeed"))
        #expect(ids.count == 8)
    }

    @Test func isoAsOfDatesReadAsDates() {
        #expect(SourcesHubMapping.asOfText("2026-10-17") == "17 Oct 2026")
        #expect(SourcesHubMapping.asOfText("Sep 2026") == "Sep 2026")
    }

    @Test func relativeTimes() {
        #expect(SourcesHubMapping.updatedText(now.addingTimeInterval(-20), now: now) == "Updated just now")
        #expect(SourcesHubMapping.updatedText(now.addingTimeInterval(-7_200), now: now) == "Updated 2 h ago")
        #expect(SourcesHubMapping.updatedText(now.addingTimeInterval(-90_000), now: now) == "Updated 1 day ago")
    }

    @Test func emptyUsedInAndBadURLAreDropped() {
        let source = HubSource(id: "boe", name: "Bank of England", kind: .live, status: .mock, gives: "Rates.", usedIn: [], url: "javascript:alert(1)")
        let card = SourcesHubMapping.card(source, now: now)
        #expect(card.usedInText == nil)
        #expect(card.url == nil)
        #expect(card.statusText == "Not live now")
    }

    // MARK: ViewModel

    @Test func viewModelLoadsFromTheClientAndOpensADetail() async {
        let model = SourcesHubViewModel(client: MockClient(streamGap: .zero), now: { SourcesHubFixtures.now })
        #expect(model.state.phase.isLoading)
        await model.load()
        #expect(model.state.phase == .ready)
        #expect(model.state.cards.count == 8)
        model.actions.onSelect("ons")
        #expect(model.selectedCard?.name == "ONS")
        var backs = 0
        model.onBack = { backs += 1 }
        model.actions.onBack()
        #expect(backs == 1)
    }

    @Test func viewModelShowsAGivenHubAtOnce() {
        let model = SourcesHubViewModel(client: MockClient(streamGap: .zero), hub: SourcesHubMock.hub(now: now), now: { SourcesHubFixtures.now })
        #expect(model.state.phase == .ready)
        #expect(model.state.cards.first?.name == "Your statement")
    }

    // MARK: Entry points

    @Test func forecastCardSaysHowManySourcesItUses() {
        let card = ForecastFixtures.card(.onTrack)
        let forecast = ForecastFixtures.forecast(.onTrack)
        let count = ForecastText.sources(forecast.sources).count
        #expect(count > 0)
        #expect(card.sourcesText == (count == 1 ? "Based on 1 source" : "Based on \(count) sources"))
        #expect(SourcesHubMapping.basedOnText(count: 0) == nil)
    }

    @Test func moneyHomeSourcesActionOpensTheHub() {
        let model = MoneyHomeViewModel(client: MockClient(streamGap: .zero))
        var opened = false
        model.onSources = { opened = true }
        model.actions.onSources()
        #expect(opened)
    }

    @Test func theMathsLinksToTheHub() {
        let model = ForecastMathsViewModel(client: MockClient(streamGap: .zero), forecast: ForecastFixtures.forecast(.onTrack))
        var opened = false
        model.onSources = { opened = true }
        model.actions.onSources()
        #expect(opened)
    }

    @Test func youDataRowRoutesToSources() {
        let model = YouViewModel(client: MockClient(streamGap: .zero))
        var route: YouViewModel.Route?
        model.onRoute = { route = $0 }
        model.actions.onOpenSources()
        #expect(route == .sources)
    }

    // MARK: Penny chips

    @Test func tryPennyHasThreeChipsMoneyLifeAndMixed() {
        #expect(PennyViewModel.onboardingChips == [
            "How does my student loan work?",
            "How do I register with a GP near uni?",
            "How can I eat well on £30 a week?",
        ])
    }

    @Test func newStringsAreTranslatedInEveryLanguage() {
        let keys: [String.LocalizationValue] = [
            "Where Penny's data comes from", "Latest values", "Open the official page", "Where the numbers come from",
            "How does my student loan work?", "How do I register with a GP near uni?", "How can I eat well on £30 a week?",
            "How much should I budget a week?", "Can I get a bursary?", "Shows the latest values", "Opens in Safari",
            "Shows where Penny's data comes from",
        ]
        for language in AppLanguage.allCases where language != .en {
            for key in keys {
                let text = L10n.tr(key, language: language)
                let english = L10n.tr(key, language: .en)
                #expect(text != english, "\(language.rawValue): \(english)")
                #expect(!text.contains("\u{2014}"))
            }
        }
    }
}

/// Screenshots of the hub and a detail for review. Off by default.
/// Run with `TEST_RUNNER_SOURCES_HUB_SNAPSHOT_DIR=<folder> make ios-test`: PNGs in English and Chinese.
@MainActor
@Suite("Sources hub snapshots", .serialized, .enabled(if: ProcessInfo.processInfo.environment["SOURCES_HUB_SNAPSHOT_DIR"] != nil))
struct SourcesHubSnapshotTests {
    let folder = URL(fileURLWithPath: ProcessInfo.processInfo.environment["SOURCES_HUB_SNAPSHOT_DIR"] ?? NSTemporaryDirectory())

    @Test(arguments: [AppLanguage.en, .zhHans])
    func screens(language: AppLanguage) async throws {
        let saved = UserDefaults.standard.string(forKey: AppLanguage.storageKey)
        AppLanguage.set(language)
        defer {
            if let saved { UserDefaults.standard.set(saved, forKey: AppLanguage.storageKey) } else { UserDefaults.standard.removeObject(forKey: AppLanguage.storageKey) }
        }
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let state = SourcesHubFixtures.ready
        try await shoot(NavigationStack { SourcesHubView(state: state) }, language, "\(language.rawValue)-1-hub")
        let boe = try #require(state.card(id: "boe"))
        try await shoot(NavigationStack { SourceDetailView(card: boe) }, language, "\(language.rawValue)-2-detail-boe")
        try await shoot(NavigationStack { SourcesHubView(state: SourcesHubFixtures.loading) }, language, "\(language.rawValue)-3-skeleton")
    }

    private func shoot(_ view: some View, _ language: AppLanguage, _ name: String) async throws {
        let scene = try #require(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let window = UIWindow(windowScene: scene)
        window.frame = scene.screen.bounds
        let host = UIHostingController(rootView: view.environment(\.appLanguage, language).environment(\.locale, language.locale))
        window.rootViewController = host
        window.makeKeyAndVisible()
        try await Task.sleep(for: .milliseconds(1200))
        let image = UIGraphicsImageRenderer(bounds: window.bounds).image { _ in
            window.drawHierarchy(in: window.bounds, afterScreenUpdates: true)
        }
        window.isHidden = true
        try #require(image.pngData()).write(to: folder.appendingPathComponent(name + ".png"))
    }
}
