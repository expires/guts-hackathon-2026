import SwiftUI

/// A friend's card in a sheet: habits as bars and, if they share it, their mix as a ring.
struct FriendDetailView: View {
    let detail: FriendDetailState
    var actions: FriendsActions = .noop
    var onClose: () -> Void = {}
    @State private var confirmRemove = false

    var body: some View {
        SheetContainer(title: detail.isMe ? "You" : detail.name, closeIdentifier: "friend.close", onClose: onClose) {
            FriendCardContent(detail: detail)
            if !detail.isMe {
                Button("Remove friend", icon: .crash) { confirmRemove = true }
                    .buttonStyle(.second)
                    .accessibilityIdentifier("friend.remove")
                    .confirmationDialog(
                        "Remove \(detail.name)?", isPresented: $confirmRemove, titleVisibility: .visible
                    ) {
                        Button("Remove", role: .destructive) { actions.onRemove(detail.id) }
                        Button("Keep", role: .cancel) {}
                    } message: {
                        Text("You will both stop seeing each other.")
                    }
            }
        }
        .background(Theme.Palette.paper)
    }
}

// MARK: - Previews

#Preview("Friend · light") { LLSheetFrame { FriendDetailView(detail: Fixtures.Friends.detailWithMix) } }
#Preview("Friend · dark") { LLSheetFrame { FriendDetailView(detail: Fixtures.Friends.detailWithMix) }.previewDark() }
#Preview("Friend · AX3") { LLSheetFrame { FriendDetailView(detail: Fixtures.Friends.detailWithMix) }.previewLargeType() }
#Preview("Friend, no mix · light") { LLSheetFrame { FriendDetailView(detail: Fixtures.Friends.detailNoMix) } }
