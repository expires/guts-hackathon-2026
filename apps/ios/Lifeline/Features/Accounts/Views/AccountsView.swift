import SwiftUI

/// Accounts: connect Monzo and Trading212, see their status, import history, disconnect.
struct AccountsView: View {
    let state: AccountsViewState
    var actions: AccountsActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        SheetContainer(title: "Accounts", closeIdentifier: "accounts.done", onClose: actions.onClose) {
            if let banner = state.banner {
                BannerView(banner: banner, onDismiss: actions.onDismissBanner)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
            switch state.phase {
            case let .loading(loading):
                LoadingStateView(state: loading)
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                ForEach(state.rows) { row in
                    AccountRowCard(row: row, state: state, actions: actions)
                }
                Text("Keys and sign-ins are checked by our server. They are never kept on your phone.")
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: state)
        .background(Theme.Palette.paper)
        .llSheet(isPresented: Binding(get: { state.trading212Form != nil }, set: { if !$0 { actions.onCancelTrading212() } })) {
            if let form = state.trading212Form {
                Trading212FormView(form: form, onSubmit: actions.onSubmitTrading212, onCancel: actions.onCancelTrading212)
            }
        }
        .confirmationDialog(
            state.disconnectPrompt?.title ?? "Disconnect?",
            isPresented: Binding(get: { state.disconnectPrompt != nil }, set: { if !$0 { actions.onCancelDisconnect() } }),
            titleVisibility: .visible,
            presenting: state.disconnectPrompt
        ) { prompt in
            Button(prompt.confirmTitle, role: .destructive, action: actions.onConfirmDisconnect)
            Button("Keep it connected", role: .cancel, action: actions.onCancelDisconnect)
        } message: { prompt in
            Text(prompt.message)
        }
    }
}

private struct BannerView: View {
    let banner: AccountsViewState.Banner
    let onDismiss: () -> Void

    private var icon: LLIcon {
        switch banner.kind {
        case .success: .check
        case .error: .crash
        case .info: .why
        }
    }

    private var fill: Color {
        switch banner.kind {
        case .success: Theme.Palette.money
        case .error: Theme.Palette.home
        case .info: Theme.Palette.work
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            LLIconImage(icon, size: 24).accessibilityHidden(true)
            Text(banner.text).font(.llBody).frame(maxWidth: .infinity, alignment: .leading)
            HeaderSquareButton(kind: .close, identifier: "accounts.banner.dismiss", action: onDismiss)
        }
        .foregroundStyle(Theme.Palette.onArea)
        .padding(.leading, Theme.Spacing.l)
        .padding(.trailing, Theme.Spacing.s)
        .padding(.vertical, Theme.Spacing.s)
        .inkSurface(.cardAlt, fill: fill)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("accounts.banner")
    }
}

private struct AccountRowCard: View {
    let row: AccountsViewState.Row
    let state: AccountsViewState
    let actions: AccountsActions

    var body: some View {
        InkCard(shape: row.id == ProviderID.monzo.rawValue ? .card : .cardAlt) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                HStack(alignment: .top, spacing: Theme.Spacing.m) {
                    LLIconImage(row.id == ProviderID.monzo.rawValue ? .bank : .investment, size: 32)
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(row.name).font(.llBodyBold)
                        Text(row.subtitle).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    StatusPill(text: row.statusText, isConnected: row.isConnected, isSample: row.isSample)
                }
                if let hint = row.hintText {
                    Text(hint).font(.llLabel.monospacedDigit()).foregroundStyle(Theme.Palette.muted)
                }
                if let history = row.historyText {
                    HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.s) {
                        LLIconImage(icon(for: row.historyKind), size: 24).accessibilityHidden(true)
                        Text(history).font(.llLabelBold)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("accounts.history.\(row.id)")
                }
                if row.id == ProviderID.monzo.rawValue {
                    if let guidance = state.monzoGuidance {
                        Label(guidance, icon: .why)
                            .font(.llLabel)
                            .accessibilityIdentifier("accounts.monzoGuidance")
                    }
                    if let note = state.approvalNote {
                        Label(note, icon: .lock)
                            .font(.llLabel)
                            .accessibilityIdentifier("accounts.approvalNote")
                    }
                    if state.showsImportNow {
                        Button {
                            actions.onImportNow()
                        } label: {
                            HStack(spacing: Theme.Spacing.s) {
                                if state.isImporting { ProgressView() }
                                Text("Import now")
                            }
                        }
                        .buttonStyle(.second)
                        .disabled(state.isImporting)
                        .accessibilityIdentifier("accounts.importNow")
                    }
                }
                actionButton
            }
        }
        .accessibilityIdentifier("accounts.row.\(row.id)")
    }

    private func icon(for kind: AccountsViewState.HistoryKind?) -> LLIcon {
        switch kind {
        case .imported: .check
        case .waitingForApproval: .statusCached
        case .problem, nil: .crash
        }
    }

    @ViewBuilder
    private var actionButton: some View {
        if row.isConnected {
            Button {
                actions.onRequestDisconnect(row.id)
            } label: {
                Text("Disconnect")
            }
            .buttonStyle(.second)
            .disabled(row.isBusy)
            .accessibilityLabel("Disconnect \(row.name)")
            .accessibilityIdentifier("accounts.disconnect.\(row.id)")
        } else {
            Button {
                row.id == ProviderID.monzo.rawValue ? actions.onConnectMonzo() : actions.onConnectTrading212()
            } label: {
                HStack(spacing: Theme.Spacing.s) {
                    if row.isBusy { ProgressView().tint(Theme.Palette.surface) }
                    Text("Connect")
                }
            }
            .buttonStyle(.main)
            .disabled(row.isBusy)
            .accessibilityLabel("Connect \(row.name)")
            .accessibilityIdentifier("accounts.connect.\(row.id)")
        }
    }
}

private struct StatusPill: View {
    let text: String
    let isConnected: Bool
    let isSample: Bool

    var body: some View {
        Chip(text: text, fill: fill)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("Status: \(text)")
    }

    private var fill: Color {
        guard isConnected else { return Theme.Palette.surface }
        return isSample ? Theme.Palette.other : Theme.Palette.money
    }
}

/// Key and secret entry. The fields live only in this sheet and are cleared as soon as they are sent.
private struct Trading212FormView: View {
    let form: AccountsViewState.Trading212Form
    let onSubmit: (String, String) -> Void
    let onCancel: () -> Void
    @State private var apiKey = ""
    @State private var apiSecret = ""

    private var canSubmit: Bool {
        !form.isSubmitting && !apiKey.trimmingCharacters(in: .whitespaces).isEmpty
            && !apiSecret.trimmingCharacters(in: .whitespaces).isEmpty
    }

    var body: some View {
        SheetContainer(title: "Connect Trading212", closeIdentifier: "trading212.cancel", onClose: onCancel) {
            Text(form.guidance).font(.llBody)
            SecretField(title: "API key", text: $apiKey, identifier: "trading212.key")
            SecretField(title: "API secret", text: $apiSecret, identifier: "trading212.secret")
            if let error = form.errorText {
                Label(error, icon: .crash)
                    .font(.llLabelBold)
                    .accessibilityIdentifier("trading212.error")
            }
            Button {
                let key = apiKey, secret = apiSecret
                apiKey = ""
                apiSecret = ""
                onSubmit(key, secret)
            } label: {
                HStack(spacing: Theme.Spacing.s) {
                    if form.isSubmitting { ProgressView().tint(Theme.Palette.surface) }
                    Text("Connect Trading212")
                }
            }
            .buttonStyle(.main)
            .disabled(!canSubmit)
            .accessibilityIdentifier("trading212.submit")
            Text("We send the key once to check it. It is not saved on your phone.")
                .font(.llLabel)
                .foregroundStyle(Theme.Palette.muted)
        }
    }
}

/// Outlined secret field in the style of `LLTextField`.
private struct SecretField: View {
    let title: String
    @Binding var text: String
    let identifier: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(title).font(.llLabelBold)
            SecureField(title, text: $text)
                .font(.llBody)
                .textContentType(.password)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .padding(.horizontal, Theme.Spacing.m)
                .frame(minHeight: Theme.buttonHeight)
                .inkSurface(.buttonAlt)
                .accessibilityIdentifier(identifier)
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Not connected · light") { AccountsView(state: Fixtures.Accounts.none) }
#Preview("Not connected · dark") { AccountsView(state: Fixtures.Accounts.none).previewDark() }
#Preview("Not connected · AX3") { AccountsView(state: Fixtures.Accounts.none).previewLargeType() }

#Preview("Connected · light") { AccountsView(state: Fixtures.Accounts.connected) }
#Preview("Connected · dark") { AccountsView(state: Fixtures.Accounts.connected).previewDark() }
#Preview("Connected · AX3") { AccountsView(state: Fixtures.Accounts.connected).previewLargeType() }

#Preview("Waiting for approval · light") { AccountsView(state: Fixtures.Accounts.waitingForApproval) }
#Preview("Waiting for approval · dark") { AccountsView(state: Fixtures.Accounts.waitingForApproval).previewDark() }
#Preview("Waiting for approval · AX3") { AccountsView(state: Fixtures.Accounts.waitingForApproval).previewLargeType() }

#Preview("Trading212 form · light") { AccountsView(state: Fixtures.Accounts.trading212Error) }
#Preview("Trading212 form · dark") { AccountsView(state: Fixtures.Accounts.trading212Error).previewDark() }
#Preview("Loading · light") { AccountsView(state: Fixtures.Accounts.loading) }
#Preview("Error · light") { AccountsView(state: Fixtures.Accounts.error) }
