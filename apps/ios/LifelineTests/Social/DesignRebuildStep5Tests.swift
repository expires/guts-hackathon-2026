import Foundation
import Testing
@testable import Lifeline

/// ADR 0026 step 5 (W7): rooms demo, You tab, paywall. Every number comes from fixtures or the API.
@MainActor
@Suite("Design rebuild step 5")
struct DesignRebuildStep5Tests {
    @Test func lobbyFromRoomFixture() throws {
        let state = RoomsFixtures.lobby
        let room = try #require(state.room)
        #expect(room.code == "LEEDS4")
        #expect(state.playersTitle == "Players · 4 of 6")
        #expect(state.startTitle == "Start with 3 players")
        #expect(state.canStart)
        #expect(state.isSampleData)
        // Born 1992, room starts 2021: age 29. 10 years: to 2031.
        #expect(state.lifeLine == "Priya, 29, nurse, Leeds. Sep 2021 to Sep 2031. Same events. Your own pace.")
        #expect(room.players.map(\.statusText) == ["Ready", "Ready", "Ready", "Joining…"])
    }

    @Test func liveRoomRivals() {
        let state = RoomsFixtures.live
        #expect(state.rivals.rivals.map(\.name) == ["You", "Ava", "Tom", "Jas"])
        #expect(state.rivals.rivals.first?.isMe == true)
        #expect(state.detail == "Age 31 · Room LEEDS4")
        #expect(state.rivalCaption.hasPrefix("Age · INDEX. Ava: Fixed for 5 years in 2021."))
    }

    @Test func resultsRankByIndex() {
        let state = RoomsFixtures.result
        #expect(state.rows.map(\.name) == ["Ava", "Tom", "You", "Jas"])
        #expect(state.winnerLine == "Ava · INDEX 131")
        #expect(state.winnerNote == "Fixed for 5 years in 2021")
        #expect(state.subtitle == "LEEDS4 · Sep 2021 to Sep 2031")
        #expect(state.shareText.contains("I came 3 of 4"))
    }

    @Test func paywallDemoPrices() {
        let state = StoreViewModel.makeState(owned: [], purchasing: nil, message: nil)
        #expect(state.products.map(\.priceText) == ["£0.99", "£1.99", "£2.99"])
        #expect(state.products.map(\.title) == ["Rewind Pass", "God Mode", "Boss Mode"])
        #expect(state.demoLabel == "Demo payment")
        #expect(state.selectedID == "lifeline.rewindpass")
        #expect(state.buyTitle == "Buy Rewind Pass · £0.99 · demo")
        let owned = StoreViewModel.makeState(owned: ["lifeline.rewindpass"], purchasing: nil, message: nil)
        #expect(owned.selectedID == "lifeline.godmode")
    }

    @Test func youTabScoresDataAndCredits() {
        let credits = CreditsFile(
            event: "GUTS Hackathon 2026",
            fonts: [.init(name: "Atkinson Hyperlegible", authors: "Braille Institute of America, Inc.", licence: "SIL Open Font License 1.1")],
            icons: "Lifeline icons"
        )
        let state = YouViewModel.makeState(
            profile: ContractExamples.financeProfile, phase: .ready, clientKind: .mock, isDebugBuild: false,
            lives: ContractExamples.lives.lives, conceptsUnlocked: 3, conceptsTotal: 40,
            sources: ContractExamples.sources, credits: credits
        )
        let best = ContractExamples.lives.lives.map(\.index).max().map { "\(Int($0.rounded()))" } ?? "-"
        #expect(state.bestIndexText == best)
        #expect(state.conceptsText == "3/40")
        #expect(state.dataRows.count == ContractExamples.sources.count)
        // Bug 7 (ADR 0053): the profile line uses onboarding's words: age, student or working, housing.
        #expect(state.personaLine.hasPrefix("Age "))
        #expect(state.credits.first?.hasSuffix("Made in 24 hours at GUTS Hackathon 2026.") == true)
        #expect(state.credits.last == "Atkinson Hyperlegible by Braille Institute of America, Inc.. SIL Open Font License 1.1.")
    }

    @Test func bundledCreditsFileLoads() throws {
        let file = try #require(CreditsFile.load())
        #expect(file.event == "GUTS Hackathon 2026")
        #expect(file.fonts.allSatisfy { $0.licence == "SIL Open Font License 1.1" })
    }
}
