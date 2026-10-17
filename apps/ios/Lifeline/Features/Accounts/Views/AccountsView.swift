import SwiftUI

/// Accounts: connect Monzo and Trading212, see their status, import history, disconnect.
struct AccountsView: View {
    let state: AccountsViewState
    var actions: AccountsActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: Theme.Spacing.l) {
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
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(Theme.Spacing.l)
            }
            .animation(Motion.standard(reduceMotion: reduceMotion), value: state)
            .navigationTitle("Accounts")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done", action: actions.onClose)
                        .frame(minWidth: Theme.minTarget, minHeight: Theme.minTarget)
                        .accessibilityIdentifier("accounts.done")
                }
            }
            .sheet(isPresented: Binding(get: { state.trading212Form != nil }, set: { if !$0 { actions.onCancelTrading212() } })) {
                if let form = state.trading212Form {
                    Trading212FormView(form: form, onSubmit: actions.onSubmitTrading212, onCancel: actions.onCancelTrading212)
                        .presentationDetents([.medium, .large])
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
}

private struct BannerView: View {
    let banner: AccountsViewState.Banner
    let onDismiss: () -> Void

    private var icon: String {
        switch banner.kind {
        case .success: "checkmark.circle.fill"
        case .error: "exclamationmark.triangle.fill"
        case .info: "info.circle.fill"
        }
    }

    private var tint: Color {
        switch banner.kind {
        case .success: .green
        case .error: .orange
        case .info: .blue
        }
    }

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            Image(systemName: icon).foregroundStyle(tint).accessibilityHidden(true)
            Text(banner.text).font(.subheadline)
            Spacer(minLength: 0)
            Button("Dismiss", systemImage: "xmark", action: onDismiss)
                .labelStyle(.iconOnly)
                .frame(minWidth: Theme.minTarget, minHeight: Theme.minTarget)
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, Theme.Spacing.s)
        .glassEffect(.regular.tint(tint.opacity(0.2)), in: .rect(cornerRadius: Theme.cornerRadius))
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("accounts.banner")
    }
}

private struct AccountRowCard: View {
    let row: AccountsViewState.Row
    let state: AccountsViewState
    let actions: AccountsActions

    var body: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                HStack(alignment: .top, spacing: Theme.Spacing.m) {
                    Image(systemName: row.systemImage)
                        .font(.title2)
                        .frame(width: 32)
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        Text(row.name).font(.headline)
                        Text(row.subtitle).font(.subheadline).foregroundStyle(.secondary)
                    }
                    Spacer(minLength: 0)
                    StatusPill(text: row.statusText, isConnected: row.isConnected, isSample: row.isSample)
                }
                if let hint = row.hintText {
                    Text(hint).font(.footnote.monospacedDigit()).foregroundStyle(.secondary)
                }
                if let history = row.historyText {
                    Label(history, systemImage: icon(for: row.historyKind))
                        .font(.footnote.weight(.medium))
                        .foregroundStyle(row.historyKind == .imported ? Color.green : Color.orange)
                        .accessibilityIdentifier("accounts.history.\(row.id)")
                }
                if row.id == ProviderID.monzo.rawValue {
                    if let guidance = state.monzoGuidance {
                        Label(guidance, systemImage: "envelope")
                            .font(.footnote)
                            .accessibilityIdentifier("accounts.monzoGuidance")
                    }
                    if let note = state.approvalNote {
                        Label(note, systemImage: "iphone.badge.checkmark")
                            .font(.footnote)
                            .accessibilityIdentifier("accounts.approvalNote")
                    }
                    if state.showsImportNow {
                        Button {
                            actions.onImportNow()
                        } label: {
                            HStack {
                                if state.isImporting { ProgressView() }
                                Text("Import now")
                            }
                            .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                        }
                        .buttonStyle(.glass)
                        .disabled(state.isImporting)
                        .accessibilityIdentifier("accounts.importNow")
                    }
                }
                actionButton
            }
        }
        .accessibilityIdentifier("accounts.row.\(row.id)")
    }

    private func icon(for kind: AccountsViewState.HistoryKind?) -> String {
        switch kind {
        case .imported: "checkmark.circle"
        case .waitingForApproval: "hourglass"
        case .problem, nil: "exclamationmark.circle"
        }
    }

    @ViewBuilder
    private var actionButton: some View {
        if row.isConnected {
            Button(role: .destructive) {
                actions.onRequestDisconnect(row.id)
            } label: {
                Text("Disconnect").frame(maxWidth: .infinity, minHeight: Theme.minTarget)
            }
            .buttonStyle(.glass)
            .disabled(row.isBusy)
            .accessibilityLabel("Disconnect \(row.name)")
            .accessibilityIdentifier("accounts.disconnect.\(row.id)")
        } else {
            Button {
                row.id == ProviderID.monzo.rawValue ? actions.onConnectMonzo() : actions.onConnectTrading212()
            } label: {
                HStack {
                    if row.isBusy { ProgressView() }
                    Text("Connect").font(.headline)
                }
                .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
            }
            .buttonStyle(.glassProminent)
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
        HStack(spacing: Theme.Spacing.xs) {
            Circle().fill(isConnected ? (isSample ? Color.gray : Color.green) : Color.secondary.opacity(0.5))
                .frame(width: 8, height: 8)
            Text(text).font(.caption.weight(.semibold))
        }
        .padding(.horizontal, Theme.Spacing.m)
        .frame(minHeight: 28)
        .glassEffect(.regular, in: .capsule)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Status: \(text)")
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
        NavigationStack {
            Form {
                Section {
                    Text(form.guidance).font(.subheadline)
                }
                Section("Your Trading212 key") {
                    SecureField("API key", text: $apiKey)
                        .textContentType(.password)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .frame(minHeight: Theme.minTarget)
                        .accessibilityIdentifier("trading212.key")
                    SecureField("API secret", text: $apiSecret)
                        .textContentType(.password)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .frame(minHeight: Theme.minTarget)
                        .accessibilityIdentifier("trading212.secret")
                }
                if let error = form.errorText {
                    Section {
                        Label(error, systemImage: "exclamationmark.triangle")
                            .foregroundStyle(.orange)
                            .accessibilityIdentifier("trading212.error")
                    }
                }
                Section {
                    Button {
                        let key = apiKey, secret = apiSecret
                        apiKey = ""
                        apiSecret = ""
                        onSubmit(key, secret)
                    } label: {
                        HStack {
                            if form.isSubmitting { ProgressView() }
                            Text("Connect Trading212").font(.headline)
                        }
                        .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                    }
                    .disabled(!canSubmit)
                    .accessibilityIdentifier("trading212.submit")
                } footer: {
                    Text("We send the key once to check it. It is not saved on your phone.")
                }
            }
            .navigationTitle("Connect Trading212")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: onCancel).frame(minHeight: Theme.minTarget)
                }
            }
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
