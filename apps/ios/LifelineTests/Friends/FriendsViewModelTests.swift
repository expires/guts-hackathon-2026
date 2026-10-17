import Foundation
import Testing
@testable import Lifeline

/// Friends tab against MockClient: leaderboard, joining, sharing, removing and the join deep link.
@MainActor
@Suite("Friends view model")
struct FriendsViewModelTests {
    @Test func loadsLeaderboardRankedWithMeHighlighted() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        let state = model.state
        #expect(state.phase == .ready)
        #expect(state.isSampleData)
        #expect(state.inviteCode == SampleFriends.myCode)
        #expect(state.rows.map(\.rank) == [1, 2, 3, 4])
        #expect(state.rows.map(\.name) == ["Sam", "You", "Priya", "Alex"])
        let me = state.rows.first { $0.isMe }
        #expect(me?.compareText == nil)
        #expect(state.rows.first?.compareText == "8 points above you")
        #expect(state.rows.last?.compareText == "19 points below you")
        #expect(state.rows.first?.growthText == "Investments: 112, started at 100")
        #expect(state.rows.last?.growthText == nil)
        #expect(state.friendCount == 3)
        #expect(state.hasGrowth)
    }

    @Test func detailShowsFactorsAndOnlySharedMix() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        let sam = model.state.detail(id: SampleFriends.sam.friendId)
        #expect(sam?.factors.first?.label == "Money you keep")
        #expect(sam?.slices.map(\.label) == ["Shares", "Bonds", "Cash"])
        #expect(sam?.mixNote == nil)
        let priya = model.state.detail(id: SampleFriends.priya.friendId)
        #expect(priya?.slices.isEmpty == true)
        #expect(priya?.mixNote == "Priya has not shared their investment mix.")
    }

    @Test func joinSucceedsAddsFriendAndClearsField() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        model.setCode("pq7w xr3n")
        #expect(model.state.add.codeInput == "PQ7WXR3N")
        #expect(model.state.add.canJoin)
        await model.join()
        #expect(model.state.friendCount == 4)
        #expect(model.state.rows.contains { $0.name == "Jo" })
        #expect(model.state.add.codeInput.isEmpty)
        #expect(model.state.add.errorText == nil)
        #expect(model.state.banner == .init(kind: .success, text: "Friend added"))
    }

    @Test func joiningYourOwnCodeSaysSoPlainly() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        model.setCode(SampleFriends.myCode)
        await model.join()
        #expect(model.state.add.errorText == "That's your own code.")
        #expect(model.state.friendCount == 3)
        #expect(model.state.banner?.kind == .failure)
    }

    @Test func joiningAnUnknownCodeSaysSo() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        model.setCode("ZZZZZZZZ")
        await model.join()
        #expect(model.state.add.errorText == "No one has that code. Check it and try again.")
        #expect(model.state.friendCount == 3)
    }

    @Test func codeFieldKeepsOnlyUnambiguousUppercaseCharacters() {
        #expect(FriendsViewModel.clean(code: "ab0o1ilc-d23456789xyz") == "ABCD2345")
        #expect(FriendsViewModel.clean(code: "abcdefghjk").count == 8)
    }

    @Test func shortCodeCannotBeSubmitted() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        model.setCode("K7M2")
        #expect(!model.state.add.canJoin)
        await model.join()
        #expect(model.state.friendCount == 3, "Nothing is sent for a short code")
        #expect(model.state.banner == nil)
    }

    @Test func rotatingGivesANewCode() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        await model.rotateCode()
        #expect(model.state.inviteCode != SampleFriends.myCode)
        #expect(model.state.add.inviteLink == "lifeline://join/\(model.state.inviteCode)")
        #expect(model.state.add.shareText.contains(model.state.inviteCode))
    }

    @Test func shareToggleShowsMixOnMyCard() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        #expect(model.state.mine.shareMix == false)
        #expect(model.state.mine.preview?.mixNote != nil)
        await model.setShareMix(true)
        #expect(model.state.mine.shareMix)
        #expect(model.state.mine.preview?.slices.isEmpty == false)
        await model.setShareMix(false)
        #expect(model.state.mine.shareMix == false)
    }

    @Test func renamingUpdatesCardAndLeaderboard() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        #expect(!model.state.mine.canSaveName)
        model.actions.onNameChange("Manu")
        #expect(model.state.mine.canSaveName)
        await model.saveName()
        #expect(model.state.mine.preview?.name == "Manu")
        #expect(!model.state.mine.canSaveName)
    }

    @Test func removingAFriendDropsThemFromTheBoard() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        await model.remove(id: SampleFriends.alex.friendId)
        #expect(model.state.friendCount == 2)
        #expect(!model.state.rows.contains { $0.name == "Alex" })
        #expect(model.state.banner?.text == "Friend removed")
    }

    @Test func noFriendsShowsEmptyBoard() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        for friend in SampleFriends.initialFriends { await model.remove(id: friend.friendId) }
        #expect(model.state.friendCount == 0)
        #expect(model.state.rows.count == 1)
        #expect(model.state.rows.first?.isMe == true)
    }

    @Test func failedLoadShowsRetryableError() async {
        let model = FriendsViewModel(client: MockClient(friendsOffline: true))
        await model.load()
        guard case let .failed(error) = model.state.phase else {
            Issue.record("Expected a failed phase")
            return
        }
        #expect(error.canRetry)
    }

    // MARK: Deep link

    @Test func joinLinkParsesAndUppercases() {
        #expect(DeepLink.parse(URL(string: "lifeline://join/pq7wxr3n")!) == .join(code: "PQ7WXR3N"))
        #expect(DeepLink.parse(URL(string: "lifeline://join/")!) == nil)
    }

    @Test func joinLinkSwitchesToFriendsTab() {
        let coordinator = AppCoordinator()
        #expect(coordinator.selectedTab == .money)
        coordinator.handle(URL(string: "lifeline://join/PQ7WXR3N")!)
        #expect(coordinator.selectedTab == .friends)
        #expect(coordinator.takeJoinCode() == "PQ7WXR3N")
        #expect(coordinator.takeJoinCode() == nil, "The code is handed over once")
    }

    @Test func connectedLinkStillOpensAccounts() {
        let coordinator = AppCoordinator()
        coordinator.handle(URL(string: "lifeline://connected?status=ok&provider=monzo")!)
        #expect(coordinator.selectedTab == .money)
        #expect(coordinator.sheet == .accounts)
    }

    @Test func deepLinkCodeIsFilledAndJoined() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        await model.handleDeepLink(code: "PQ7WXR3N")
        #expect(model.state.rows.contains { $0.name == "Jo" })
        #expect(model.state.banner == .init(kind: .success, text: "Friend added"))
    }

    @Test func deepLinkWithBadCodeShowsFailure() async {
        let model = FriendsViewModel(client: MockClient())
        await model.load()
        await model.handleDeepLink(code: "ZZZZZZZZ")
        #expect(model.state.banner?.kind == .failure)
        #expect(model.state.friendCount == 3)
    }

    @Test func friendsTabIsBetweenMoneyAndYou() {
        let tabs = AppFeatures.visibleTabs
        #expect(tabs.first == .money)
        #expect(tabs.last == .you)
        #expect(tabs.contains(.friends))
        #expect(AppTab.friends.title == "Friends")
    }

    @Test func comparisonWording() {
        #expect(FriendsViewModel.compareText(theirs: 68, mine: 67) == "1 point above you")
        #expect(FriendsViewModel.compareText(theirs: 60, mine: 67) == "7 points below you")
        #expect(FriendsViewModel.compareText(theirs: 67, mine: 67) == "Same score as you")
        #expect(FriendsViewModel.compareText(theirs: nil, mine: 67) == nil)
    }
}
