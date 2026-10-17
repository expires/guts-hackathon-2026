import SwiftUI

/// Account: profile, sign out, delete account (asks first), demo reset. Design system only.
struct AccountView: View {
    let state: AccountViewState
    var actions: AccountActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(
                    title: "Account",
                    leading: actions.onClose.map { close in HeaderSquareButton(kind: .back, identifier: "account.back", action: close) }
                ) {
                    if state.isSampleData { DemoDataBadge() }
                }
                switch state.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    if let profile = state.profile { content(profile) }
                }
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s).padding(.bottom, Theme.Spacing.m)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    @ViewBuilder
    private func content(_ profile: AccountViewState.Profile) -> some View {
        HStack(spacing: Theme.Spacing.m) {
            PennyView(mood: .smiling, size: 56)
            VStack(alignment: .leading, spacing: 2) {
                Text(profile.name).font(.llTitle).accessibilityIdentifier("account.name")
                Text(profile.signInText).font(.llBody)
                if !profile.sinceText.isEmpty {
                    Text(profile.sinceText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
            }
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.card)
        .accessibilityElement(children: .combine)
        RowGroup(title: "Your money data") {
            if profile.dataSources.isEmpty {
                ListRow(icon: .lock, title: "No money data yet", subtitle: "Connect your money to get a Next Move.", showsChevron: false)
            } else {
                ForEach(profile.dataSources, id: \.self) { source in
                    ListRow(icon: .check, title: source, showsChevron: false)
                }
            }
        }
        .accessibilityIdentifier("account.data")
        if let message = state.message {
            Text(message).font(.llBodyBold).accessibilityIdentifier("account.message")
        }
        if let error = state.errorMessage {
            OnboardingErrorCard(message: error, onDismiss: actions.onCancel)
        }
        if let confirm = state.confirm {
            confirmCard(confirm)
        } else {
            VStack(spacing: Theme.Spacing.s) {
                Button("Reset the demo") { actions.onAsk(.reset) }
                    .buttonStyle(.second)
                    .accessibilityIdentifier("account.reset")
                Button("Sign out") { actions.onAsk(.signOut) }
                    .buttonStyle(SecondButtonStyle(shape: .buttonThird))
                    .accessibilityIdentifier("account.signOut")
                Button("Delete my account") { actions.onAsk(.delete) }
                    .buttonStyle(.text)
                    .foregroundStyle(Theme.Palette.ink)
                    .accessibilityIdentifier("account.delete")
            }
        }
    }

    /// Own confirm card (no system alert): what happens, then the action and Cancel.
    private func confirmCard(_ confirm: AccountViewState.Confirm) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Text(confirm.title).font(.llTitle).accessibilityAddTraits(.isHeader)
            Text(confirm.message).font(.llBody).fixedSize(horizontal: false, vertical: true)
            PrimaryButton(title: confirm.button, isBusy: state.isBusy, action: actions.onConfirm)
                .disabled(state.isBusy)
                .accessibilityIdentifier("account.confirm")
            Button("Cancel", action: actions.onCancel)
                .buttonStyle(.second)
                .disabled(state.isBusy)
                .accessibilityIdentifier("account.cancel")
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.hero, fill: confirm == .delete ? Theme.Palette.health : Theme.Palette.surface, hero: true)
        .foregroundStyle(confirm == .delete ? Theme.Palette.onArea : Theme.Palette.ink)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("account.confirmCard")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") { AccountView(state: AccountFixtures.ready) }
#Preview("Ready · dark") { AccountView(state: AccountFixtures.ready).previewDark() }
#Preview("Ready · AX3") { AccountView(state: AccountFixtures.ready).previewLargeType() }
#Preview("Confirm delete · light") { AccountView(state: AccountFixtures.confirmDelete) }
#Preview("Confirm delete · dark") { AccountView(state: AccountFixtures.confirmDelete).previewDark() }
#Preview("After reset · light") { AccountView(state: AccountFixtures.afterReset) }
#Preview("Loading · light") { AccountView(state: AccountFixtures.loading) }
#Preview("Offline · dark") { AccountView(state: AccountFixtures.error).previewDark() }
