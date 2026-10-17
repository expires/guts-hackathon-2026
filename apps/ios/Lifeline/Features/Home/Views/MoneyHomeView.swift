// Draft by W6. Owned by the UI owner from creation.
import SwiftUI

/// Money tab (ADR 0016): connect accounts, Next Move, investments, habits, Guess my spend and the widgets.
struct MoneyHomeView: View {
    let state: MoneyHomeViewState
    var actions: MoneyHomeActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.l) {
                if let status = state.dataStatusText {
                    dataStatus(status)
                }
                if state.connections.isLoaded {
                    if state.connections.anyConnected {
                        accountsRow
                    } else {
                        connectCard
                    }
                }
                NextMoveCardView(state: state.nextMove, actions: actions.nextMove)
                navigationCard(
                    title: "Your investments",
                    detail: state.investmentsLink?.text ?? "See what you own and replay your ISA through the past.",
                    systemImage: "chart.pie",
                    identifier: "money.investments",
                    action: actions.onOpenInvestments
                )
                navigationCard(
                    title: "Your money habits",
                    detail: "A score for how you save and spend, with a reason for each part.",
                    systemImage: "heart.text.square",
                    identifier: "money.habits",
                    action: actions.onOpenHabits
                )
                GuessSpendCardView(state: state.guess, actions: actions.guess)
                MoneyWidgetsView(state: state.widgets, actions: actions.widgets)
            }
            .padding(Theme.Spacing.l)
            .animation(Motion.standard(reduceMotion: reduceMotion), value: state.connections)
        }
        .refreshable { await actions.onRefresh() }
        .navigationTitle("Money")
    }

    @ViewBuilder
    private func dataStatus(_ text: String) -> some View {
        if state.isSampleData {
            DemoDataBadge()
                .frame(maxWidth: .infinity, alignment: .leading)
        } else {
            Label(text, systemImage: "bolt.horizontal.circle")
                .font(.caption.weight(.semibold))
                .foregroundStyle(.green)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityLabel("Live data. From your connected accounts.")
                .accessibilityIdentifier("money.liveBadge")
        }
    }

    private var connectCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Label("Connect your accounts", systemImage: "link.circle.fill")
                    .font(.title3.bold())
                Text("Link Monzo and Trading212 to see your own money here. Until then you are looking at sample data.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                PrimaryButton(title: "Connect your accounts", systemImage: "link", action: actions.onOpenAccounts)
                    .accessibilityIdentifier("money.connectAccounts")
            }
        }
        .accessibilityElement(children: .contain)
    }

    private var accountsRow: some View {
        Button(action: actions.onOpenAccounts) {
            HStack(spacing: Theme.Spacing.m) {
                Image(systemName: "link").accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Accounts").font(.headline)
                    Text(state.connections.summaryText).font(.footnote).foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right").font(.footnote).foregroundStyle(.tertiary).accessibilityHidden(true)
            }
            .padding(Theme.Spacing.l)
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .contentShape(.rect(cornerRadius: Theme.cornerRadius))
            .glassEffect(.regular.interactive(), in: .rect(cornerRadius: Theme.cornerRadius))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Accounts. \(state.connections.summaryText)")
        .accessibilityIdentifier("money.accounts")
    }

    private func navigationCard(title: String, detail: String, systemImage: String, identifier: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.m) {
                Image(systemName: systemImage).font(.title2).frame(width: 32).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.headline)
                    Text(detail).font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.leading)
                }
                Spacer()
                Image(systemName: "chevron.right").font(.footnote).foregroundStyle(.tertiary).accessibilityHidden(true)
            }
            .padding(Theme.Spacing.l)
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .contentShape(.rect(cornerRadius: Theme.cornerRadius))
            .glassEffect(.regular.interactive(), in: .rect(cornerRadius: Theme.cornerRadius))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(title). \(detail)")
        .accessibilityIdentifier(identifier)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Nothing connected · light") { MoneyHomeView(state: Fixtures.MoneyHome.ready).previewInNavigation() }
#Preview("Nothing connected · dark") { MoneyHomeView(state: Fixtures.MoneyHome.ready).previewInNavigation().previewDark() }
#Preview("Nothing connected · AX3") { MoneyHomeView(state: Fixtures.MoneyHome.ready).previewInNavigation().previewLargeType() }

#Preview("Connected, live · light") { MoneyHomeView(state: Fixtures.MoneyHome.connectedLive).previewInNavigation() }
#Preview("Connected, live · dark") { MoneyHomeView(state: Fixtures.MoneyHome.connectedLive).previewInNavigation().previewDark() }
#Preview("Connected, live · AX3") { MoneyHomeView(state: Fixtures.MoneyHome.connectedLive).previewInNavigation().previewLargeType() }

#Preview("Loading · light") { MoneyHomeView(state: Fixtures.MoneyHome.loading).previewInNavigation() }
#Preview("Offline · light") { MoneyHomeView(state: Fixtures.MoneyHome.offline).previewInNavigation() }
