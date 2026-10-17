import SwiftUI
import UIKit

/// Add a friend: share your code, or enter theirs.
struct AddFriendView: View {
    let state: AddFriendState
    var actions: FriendsActions = .noop
    var onClose: () -> Void = {}
    @FocusState private var codeFocused: Bool

    var body: some View {
        SheetContainer(title: "Add a friend", closeIdentifier: "addFriend.close", onClose: onClose) {
            yourCode
            enterCode
        }
        .background(Theme.Palette.paper)
    }

    private var yourCode: some View {
        InkCard(shape: .hero, hero: true, padding: Theme.Spacing.xl) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text("Your code").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                Text(state.inviteCode)
                    .font(.llHero.monospaced())
                    .tracking(2)
                    .lineLimit(1)
                    .minimumScaleFactor(0.5)
                    .textSelection(.enabled)
                    .accessibilityLabel("Your code")
                    .accessibilityValue(state.inviteCode.map(String.init).joined(separator: " "))
                    .accessibilityIdentifier("addFriend.code")
                Text("Give this to a friend. They type it in, or open the link you share. They only ever see your scores, never your amounts.")
                    .font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
                HStack(spacing: Theme.Spacing.s) {
                    Button {
                        UIPasteboard.general.string = state.inviteCode
                        actions.onCopied()
                    } label: {
                        Label("Copy code", systemImage: "doc.on.doc")
                    }
                    .buttonStyle(.second)
                    .accessibilityIdentifier("addFriend.copy")
                    ShareLink(item: state.shareText, subject: Text("Compare money habits")) {
                        Label("Share", systemImage: "square.and.arrow.up")
                    }
                    .buttonStyle(.main)
                    .accessibilityIdentifier("addFriend.share")
                }
                Button {
                    actions.onRotate()
                } label: {
                    if state.isRotating {
                        ProgressView()
                    } else {
                        Text("Get a new code")
                    }
                }
                .buttonStyle(.text)
                .disabled(state.isRotating)
                .accessibilityHint("Your old code stops working.")
                .accessibilityIdentifier("addFriend.rotate")
            }
        }
        .padding(.trailing, Theme.heroShadow.width)
        .padding(.bottom, Theme.heroShadow.height)
    }

    private var enterCode: some View {
        InkCard(shape: .cardAlt) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text("Enter a friend's code").font(.llBodyBold).accessibilityAddTraits(.isHeader)
                Text("It has 8 letters and numbers.").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                TextField("For example K7M2QX9P", text: Binding(get: { state.codeInput }, set: actions.onCodeChange))
                    .font(.llBodyBold.monospaced())
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                    .keyboardType(.asciiCapable)
                    .submitLabel(.join)
                    .focused($codeFocused)
                    .onSubmit { if state.canJoin { actions.onJoin() } }
                    .padding(.horizontal, Theme.Spacing.m)
                    .frame(minHeight: Theme.buttonHeight)
                    .inkSurface(.buttonAlt)
                    .accessibilityLabel("Friend's code")
                    .accessibilityIdentifier("addFriend.input")
                if let error = state.errorText {
                    Label(error, icon: .why)
                        .font(.llLabelBold)
                        .foregroundStyle(Theme.Palette.ink)
                        .accessibilityIdentifier("addFriend.error")
                }
                PrimaryButton(title: state.isJoining ? "Adding" : "Add friend", isBusy: state.isJoining) {
                    codeFocused = false
                    actions.onJoin()
                }
                .disabled(!state.canJoin)
                .accessibilityIdentifier("addFriend.join")
            }
        }
    }
}

// MARK: - Previews

#Preview("Add friend · light") { LLSheetFrame { AddFriendView(state: Fixtures.Friends.add) } }
#Preview("Add friend, error · light") { LLSheetFrame { AddFriendView(state: Fixtures.Friends.addError) } }
#Preview("Add friend · dark") { LLSheetFrame { AddFriendView(state: Fixtures.Friends.add) }.previewDark() }
#Preview("Add friend · AX3") { LLSheetFrame { AddFriendView(state: Fixtures.Friends.add) }.previewLargeType() }
