import SwiftUI

/// Connect a bank to fill in "Play yourself".
struct BankConnectView: View {
    let state: BankConnectViewState
    var actions: BankConnectActions = .noop

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                    Image(systemName: "building.columns.fill")
                        .font(.system(size: 48))
                        .foregroundStyle(.tint)
                        .accessibilityHidden(true)
                    Text("Fill in from your bank").font(.largeTitle.bold())
                    Text(state.privacyNote).foregroundStyle(.secondary)

                    switch state.step {
                    case .intro:
                        PrimaryButton(title: "Connect \(state.providerName)", systemImage: "link", action: actions.onConnect)
                            .accessibilityIdentifier("bank.connect")
                    case .connecting:
                        LoadingStateView(state: .init(message: "Waiting for your bank"))
                    case .connected:
                        if let summary = state.summary {
                            GlassCard {
                                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                                    if state.status == .mock {
                                        DemoDataBadge()
                                    }
                                    LabeledContent("Accounts", value: "\(summary.accounts)")
                                    LabeledContent("Pay per year", value: Money.format(summary.annualIncome))
                                    LabeledContent("Savings", value: Money.format(summary.savings))
                                    LabeledContent("Home", value: summary.housingLabel)
                                    LabeledContent("Region", value: summary.regionLabel)
                                }
                            }
                            PrimaryButton(title: "Use these numbers", systemImage: "checkmark", action: actions.onUseProfile)
                                .accessibilityIdentifier("bank.useProfile")
                        }
                    case let .failed(error):
                        ErrorStateView(state: error, onRetry: actions.onConnect)
                    }
                }
                .padding(Theme.Spacing.l)
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: actions.onClose)
                }
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Intro · light") {
    BankConnectView(state: Fixtures.Bank.intro)
}

#Preview("Intro · dark") {
    BankConnectView(state: Fixtures.Bank.intro).previewDark()
}

#Preview("Intro · AX3") {
    BankConnectView(state: Fixtures.Bank.intro).previewLargeType()
}

#Preview("Connecting · light") {
    BankConnectView(state: Fixtures.Bank.connecting)
}

#Preview("Connecting · dark") {
    BankConnectView(state: Fixtures.Bank.connecting).previewDark()
}

#Preview("Connecting · AX3") {
    BankConnectView(state: Fixtures.Bank.connecting).previewLargeType()
}

#Preview("Connected · light") {
    BankConnectView(state: Fixtures.Bank.connected)
}

#Preview("Connected · dark") {
    BankConnectView(state: Fixtures.Bank.connected).previewDark()
}

#Preview("Connected · AX3") {
    BankConnectView(state: Fixtures.Bank.connected).previewLargeType()
}

#Preview("Failed · light") {
    BankConnectView(state: Fixtures.Bank.failed)
}

#Preview("Failed · dark") {
    BankConnectView(state: Fixtures.Bank.failed).previewDark()
}

#Preview("Failed · AX3") {
    BankConnectView(state: Fixtures.Bank.failed).previewLargeType()
}
