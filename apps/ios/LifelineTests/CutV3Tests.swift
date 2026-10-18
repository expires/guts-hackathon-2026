import Foundation
import Testing
@testable import Lifeline

/// PENNY_V3_BUILD F (the cut), E5 and the You tab changes (B4, B5, G1, G4, G5).
@MainActor
@Suite("Penny V3 cut and You tab")
struct CutV3Tests {
    @Test func cutFlagIsOffByDefault() {
        #expect(!FeatureFlags.showsCutFeatures)
    }

    @Test func playStateHidesCutFeaturesByDefault() {
        #expect(!Fixtures.Play.ready.showsCutFeatures)
    }

    @Test func youShowsLessonsNotConcepts() {
        let state = YouViewModel.makeState(
            profile: ContractExamples.financeProfile, phase: .ready, clientKind: .mock, isDebugBuild: false,
            lessons: (3, 48)
        )
        #expect(state.lessonsText == "3/48")
        #expect(YouViewModel.lessonsText(nil) == "-")
        #expect(YouViewModel.lessonsText((0, 0)) == "-")
    }

    @Test func youHasTheHonestyLineAndNoDataTag() {
        let state = YouViewModel.makeState(profile: nil, phase: .ready, clientKind: .mock, isDebugBuild: false)
        #expect(state.honestyText.hasPrefix("These are sample students."))
        #expect(state.honestyText.contains("sample statements built from real UK figures"))
        #expect(state.dataBadgeText == nil)
    }

    @Test func youHidesCutRowsByDefault() {
        let state = YouViewModel.makeState(profile: nil, phase: .ready, clientKind: .mock, isDebugBuild: false, evaluationCount: 50)
        #expect(!state.showsCutFeatures)
        #expect(!state.showsEvaluation)
        #expect(!state.showsDebugMenu)
    }

    @Test func dataRowsAreStudentFacingOnly() throws {
        let ids = ["fred", "boe-mpc", "landregistry", "ons", "monzo", "boe", "coingecko", "frankfurter", "octopus", "nomis"]
        let json = "[" + ids.map { id in
            #"{"id":"\#(id)","name":"\#(id) raw","status":"\#(id == "fred" || id == "ons" ? "mock" : "live")","ttl_seconds":3600,"coverage":"UK","attribution":"x","licence":"OGL"}"#
        }.joined(separator: ",") + "]"
        let sources = try JSONDecoder().decode([SourceStatus].self, from: Data(json.utf8))
        let rows = YouViewModel.dataRows(sources)
        #expect(rows.map(\.id) == ["facts", "boe", "ons", "nomis", "octopus", "frankfurter", "boe-mpc"])
        #expect(rows.map(\.name) == [
            "Official facts (gov.uk, SAAS, Student Finance)", "Bank of England", "ONS", "Nomis", "Octopus Energy",
            "Frankfurter", "Bank of England MPC dates",
        ])
        #expect(!rows.contains { $0.detail.localizedCaseInsensitiveContains("mock") })
        #expect(rows.first { $0.id == "ons" }?.detail == "Not live now")
    }

    @Test func creditsHaveNoMockData() throws {
        let credits = try #require(CreditsFile.load())
        let lines = YouViewModel.creditLines(credits)
        #expect(!lines.isEmpty)
        #expect(!lines.contains { $0.localizedCaseInsensitiveContains("mock data") })
    }

    @Test func habitNamesAreTheOneSet() {
        #expect(YouViewModel.habitNames.map(\.name) == [
            "Saving", "Safety cushion", "Steady spending", "Needs before wants", "Subscriptions in check", "Low debt pressure",
        ])
    }

    @Test func headerUsesTheStudentNameNeverYou() {
        var profile = ContractExamples.financeProfile
        let real = YouViewModel.profile(profile)
        #expect(real.name == profile.character.name)
        profile.character.name = "You"
        #expect(YouViewModel.profile(profile, displayName: "Eilidh").name == "Eilidh")
    }

    @Test func safetyBufferSavesAndShows() async {
        let model = YouViewModel(client: MockClient(data: .recorded))
        await model.load()
        let start = model.state.buffer?.selected
        #expect(start != nil)
        let target = start == 15 ? 5 : 15
        await model.setBuffer(target)
        #expect(model.state.buffer?.selected == target)
        #expect(model.state.buffer?.isSaving == false)
        #expect(model.state.buffer?.errorText == nil)
        await model.setBuffer(7)
        #expect(model.state.buffer?.selected == target, "Only 0, 5, 10, 15 or 20")
    }
}
