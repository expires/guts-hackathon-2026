import Foundation

// MARK: - Friends

extension Fixtures {
    @MainActor
    enum Friends {
        private static var board: Leaderboard {
            SampleFriends.leaderboard(me: SampleFriends.me(), friends: SampleFriends.initialFriends, code: SampleFriends.myCode)
        }

        static var loaded: FriendsViewState {
            FriendsViewModel.makeState(board: board, myCard: SampleFriends.me(), phase: .ready, nameDraft: "You")
        }

        /// A friend was just added.
        static var added: FriendsViewState {
            FriendsViewModel.makeState(
                board: board, myCard: SampleFriends.me(), phase: .ready,
                banner: .init(kind: .success, text: "Friend added"), nameDraft: "You"
            )
        }

        static var empty: FriendsViewState {
            let alone = SampleFriends.leaderboard(me: SampleFriends.me(), friends: [], code: SampleFriends.myCode)
            return FriendsViewModel.makeState(board: alone, myCard: SampleFriends.me(), phase: .ready, nameDraft: "You")
        }

        static var loading: FriendsViewState {
            FriendsViewModel.makeState(
                board: nil, myCard: nil, phase: .loading(.init(message: FriendsViewModel.loadingMessage))
            )
        }

        static var error: FriendsViewState {
            FriendsViewModel.makeState(board: nil, myCard: nil, phase: .failed(Fixtures.networkError))
        }

        static var detailWithMix: FriendDetailState { FriendsViewModel.detail(for: SampleFriends.sam, isMe: false) }
        static var detailNoMix: FriendDetailState { FriendsViewModel.detail(for: SampleFriends.priya, isMe: false) }

        static var add: AddFriendState {
            FriendsViewModel.makeState(
                board: board, myCard: SampleFriends.me(), phase: .ready, codeInput: "PQ7W"
            ).add
        }

        static var addError: AddFriendState {
            FriendsViewModel.makeState(
                board: board, myCard: SampleFriends.me(), phase: .ready, codeInput: "ZZZZZZZZ",
                joinError: "No one has that code. Check it and try again."
            ).add
        }

        static var mineHidden: MyCardState {
            FriendsViewModel.makeState(board: board, myCard: SampleFriends.me(), phase: .ready, nameDraft: "You").mine
        }

        static var mineShared: MyCardState {
            let shared = SampleFriends.me(name: "Manu", shareMix: true)
            return FriendsViewModel.makeState(board: board, myCard: shared, phase: .ready, nameDraft: "Manu").mine
        }
    }
}
