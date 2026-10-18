import SwiftUI

/// The connect step: Monzo, Trading 212, Upload a statement, Enter your numbers, each with its status.
/// One view for "Play as yourself" (with Continue) and You > Connect your money (without).
struct ConnectionsView: View {
    let state: ConnectionsViewState
    var title = L10n.tr("Connect your money")
    var actions: ConnectionsActions = .noop

    var body: some View {
        VStack(spacing: 0) {
            ScreenHeader(title: title, leading: HeaderSquareButton(kind: .back, identifier: "connections.back", action: actions.onClose))
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.top, Theme.Spacing.s)
                .padding(.bottom, Theme.Spacing.xs)
            switch state.phase {
            case .loading:
                ScrollView { SkeletonList(rows: 4).padding(Theme.Spacing.margin) }
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                content
            }
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
        .sheet(isPresented: Binding(
            get: { state.trading212.isPresented },
            set: { if !$0 { actions.onCloseTrading212() } }
        )) {
            Trading212SheetView(sheet: state.trading212, onSubmit: actions.onSubmitTrading212, onClose: actions.onCloseTrading212)
                .presentationDetents([.large])
        }
        .sheet(isPresented: Binding(
            get: { state.monzoWait != nil },
            set: { _ in } // Only the buttons close it.
        )) {
            if let wait = state.monzoWait {
                MonzoWaitSheetView(wait: wait, onReopen: actions.onMonzoReopen, onCancel: actions.onMonzoCancel, onRetry: actions.onMonzoRetry)
                    .presentationDetents([.medium])
                    .interactiveDismissDisabled()
            }
        }
        .confirmationDialog(
            L10n.tr("Disconnect \(state.pendingDisconnect?.title ?? "")?"),
            isPresented: Binding(
                get: { state.pendingDisconnect != nil },
                set: { if !$0 { actions.onCancelDisconnect() } }
            ),
            titleVisibility: .visible
        ) {
            Button(L10n.tr("Disconnect"), role: .destructive, action: actions.onConfirmDisconnect)
            Button(L10n.tr("Keep it connected"), role: .cancel, action: actions.onCancelDisconnect)
        } message: {
            Text("Penny stops reading it and removes the data it brought in. You can connect it again later.")
        }
    }

    private var content: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                if let note = state.sampleNote {
                    Text(note).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("connections.sampleNote")
                }
                if let message = state.errorMessage {
                    banner(message, fill: Theme.Palette.health, identifier: "connections.error")
                }
                if let notice = state.notice {
                    banner(notice, fill: Theme.Palette.money, identifier: "connections.notice")
                }
                ForEach(state.rows) { row in
                    ConnectionRow(row: row, isHighlighted: state.highlighted == row.kind, isBusy: state.isBusy, actions: actions)
                }
                Text("Penny only reads. Your keys stay on our server, never in the app.")
                    .font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
                if let continueTitle = state.continueTitle {
                    PrimaryButton(title: continueTitle, action: actions.onContinue)
                        .padding(.top, Theme.Spacing.s)
                        .accessibilityIdentifier("connections.continue")
                }
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xl)
        }
        .scrollIndicators(.hidden)
    }

    private func banner(_ text: String, fill: Color, identifier: String) -> some View {
        Text(text)
            .font(.llBody)
            .foregroundStyle(Theme.Palette.onArea)
            .padding(Theme.Spacing.l)
            .frame(maxWidth: .infinity, alignment: .leading)
            .inkSurface(.cardAlt, fill: fill)
            .onTapGesture(perform: actions.onDismissError)
            .accessibilityIdentifier(identifier)
    }
}

/// One option: title, status, what it gave us, and its buttons.
private struct ConnectionRow: View {
    let row: ConnectionsViewState.Row
    let isHighlighted: Bool
    let isBusy: Bool
    let actions: ConnectionsActions

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            HStack(alignment: .top, spacing: Theme.Spacing.m) {
                LLIconImage(icon, size: 32)
                VStack(alignment: .leading, spacing: 2) {
                    Text(row.title).font(.llBodyBold)
                    Text(row.detail ?? row.subtitle).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                VStack(alignment: .trailing, spacing: 4) {
                    Chip(text: row.statusText, fill: row.isConnected ? Theme.Palette.money : Theme.Palette.surface)
                        .accessibilityIdentifier("connections.status.\(row.kind.rawValue)")
                    if let badge = row.badge { Chip(text: badge) }
                }
            }
            HStack(spacing: Theme.Spacing.s) {
                if row.isConnected {
                    Button(row.connectTitle) { actions.onConnect(row.kind) }
                        .buttonStyle(.second)
                        .disabled(isBusy)
                        .accessibilityIdentifier("connections.connect.\(row.kind.rawValue)")
                } else {
                    Button(row.connectTitle) { actions.onConnect(row.kind) }
                        .buttonStyle(.main)
                        .disabled(isBusy)
                        .accessibilityIdentifier("connections.connect.\(row.kind.rawValue)")
                }
                if row.canDisconnect {
                    Button(L10n.tr("Disconnect")) { actions.onDisconnect(row.kind) }
                        .buttonStyle(.second)
                        .disabled(isBusy)
                        .accessibilityIdentifier("connections.disconnect.\(row.kind.rawValue)")
                }
            }
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .foregroundStyle(Theme.Palette.ink)
        .inkSurface(.card, fill: isHighlighted ? ForecastPalette.orangeTint : Theme.Palette.surface)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("connections.row.\(row.kind.rawValue)")
    }

    private var icon: LLIcon {
        switch row.kind {
        case .monzo: .bank
        case .trading212: .investment
        case .statement: .bills
        case .manual: .budget
        }
    }
}

// MARK: - Previews

#Preview("Nothing connected · light") {
    ConnectionsView(state: ConnectionsPreviews.nothing, actions: .noop)
}
#Preview("Connected · light") {
    ConnectionsView(state: ConnectionsPreviews.connected, actions: .noop)
}
#Preview("Connected · dark") {
    ConnectionsView(state: ConnectionsPreviews.connected, actions: .noop).previewDark()
}
#Preview("Play as yourself · AX3") {
    ConnectionsView(state: ConnectionsPreviews.withContinue, actions: .noop).previewLargeType()
}
#Preview("Sample student · light") {
    ConnectionsView(state: ConnectionsPreviews.sample, actions: .noop)
}
#Preview("Disconnect · light") {
    ConnectionsView(state: ConnectionsPreviews.confirming, actions: .noop)
}
#Preview("Loading · light") {
    ConnectionsView(state: ConnectionsViewState(), actions: .noop)
}
