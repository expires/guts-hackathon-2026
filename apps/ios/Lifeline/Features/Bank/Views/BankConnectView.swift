import SwiftUI

/// Connect a bank to fill in "Play yourself".
struct BankConnectView: View {
    let state: BankConnectViewState
    var actions: BankConnectActions = .noop
    @Environment(\.llPresentationMode) private var presentation

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: "Your bank", icon: .bank) {
                    HeaderSquareButton(kind: .close, identifier: "bank.close", action: actions.onClose)
                }
                Text("Fill in from your bank")
                    .font(.llHero)
                    .fixedSize(horizontal: false, vertical: true)
                Text(state.privacyNote)
                    .font(.llBody)
                    .foregroundStyle(Theme.Palette.muted)
                    .fixedSize(horizontal: false, vertical: true)

                switch state.step {
                case .intro:
                    PrimaryButton(title: "Connect \(state.providerName)", icon: .bank, action: actions.onConnect)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .accessibilityIdentifier("bank.connect")
                case .connecting:
                    LoadingStateView(state: .init(message: "Waiting for your bank"))
                case .connected:
                    if let summary = state.summary {
                        InkCard {
                            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                                if state.status == .mock {
                                    DemoDataBadge()
                                }
                                row("Accounts", "\(summary.accounts)")
                                row("Pay per year", summary.annualIncome.formatted(.llAmount(presentation: presentation)))
                                row("Savings", summary.savings.formatted(.llAmount(presentation: presentation)))
                                row("Home", summary.housingLabel)
                                row("Region", summary.regionLabel)
                            }
                        }
                        PrimaryButton(title: "Use these numbers", icon: .check, action: actions.onUseProfile)
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                            .accessibilityIdentifier("bank.useProfile")
                    }
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onConnect)
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
    }

    private func row(_ title: String, _ value: String) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title).font(.llBody).foregroundStyle(Theme.Palette.muted)
            Spacer(minLength: Theme.Spacing.m)
            Text(value).font(.llBodyBold).multilineTextAlignment(.trailing)
        }
        .accessibilityElement(children: .combine)
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
