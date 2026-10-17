import SwiftUI

/// Sheets the Friends tab can open.
enum FriendsSheet: Identifiable, Hashable {
    case add
    case mine
    case friend(String)

    var id: String {
        switch self {
        case .add: "add"
        case .mine: "mine"
        case let .friend(id): "friend.\(id)"
        }
    }
}

/// Glue: owns `FriendsViewModel`, feeds the Friends views and picks up `lifeline://join/CODE` links.
struct FriendsScreen: View {
    @Environment(AppCoordinator.self) private var coordinator
    @State private var model: FriendsViewModel
    @State private var sheet: FriendsSheet?

    init(client: any LifelineClient) {
        _model = State(initialValue: FriendsViewModel(client: client))
    }

    var body: some View {
        FriendsView(state: model.state, actions: actions)
            .task {
                await model.load()
                await takeLink()
            }
            .onChange(of: coordinator.pendingJoinCode) {
                Task { await takeLink() }
            }
            .llSheet(item: $sheet) { sheet in
                switch sheet {
                case .add:
                    AddFriendView(state: model.state.add, actions: actions) { self.sheet = nil }
                case .mine:
                    WhatFriendsSeeView(state: model.state.mine, actions: actions) { self.sheet = nil }
                case let .friend(id):
                    if let detail = model.state.detail(id: id) {
                        FriendDetailView(
                            detail: detail,
                            actions: FriendsActions(onRemove: { removeID in
                                self.sheet = nil
                                model.actions.onRemove(removeID)
                            })
                        ) { self.sheet = nil }
                    }
                }
            }
    }

    /// A join link opens the tab, then fills in the code and adds the friend.
    private func takeLink() async {
        guard let code = coordinator.takeJoinCode() else { return }
        sheet = nil
        await model.handleDeepLink(code: code)
    }

    private var actions: FriendsActions {
        var actions = model.actions
        actions.onSelect = { sheet = .friend($0) }
        actions.onOpenAdd = { sheet = .add }
        actions.onOpenMine = { sheet = .mine }
        actions.onJoin = {
            Task {
                await model.join()
                if model.state.add.errorText == nil { sheet = nil }
            }
        }
        return actions
    }
}
