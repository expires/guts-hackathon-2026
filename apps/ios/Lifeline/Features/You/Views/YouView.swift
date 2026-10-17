// Draft by W6. Owned by the UI owner from creation.
import SwiftUI

/// You tab (ADR 0016): your profile, connected accounts, data sources and settings.
struct YouView: View {
    let state: YouViewState
    var actions: YouActions = .noop

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.l) {
                switch state.profilePhase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    if let profile = state.profile { profileCard(profile) }
                    if !state.personalFacts.isEmpty { factsCard }
                }
                GlassCard {
                    VStack(alignment: .leading, spacing: 0) {
                        row(title: "Accounts", detail: state.bankText, systemImage: "link", identifier: "you.accounts", action: actions.onConnectBank)
                        Divider()
                        row(title: "Where the numbers come from", detail: nil, systemImage: "doc.text.magnifyingglass", identifier: "you.sources", action: actions.onOpenSources)
                        Divider()
                        row(title: "Store", detail: nil, systemImage: "bag", identifier: "you.store", action: actions.onOpenStore)
                        if state.showsDebugMenu {
                            Divider()
                            row(title: "Debug menu", detail: "Client: \(state.clientText)", systemImage: "ladybug", identifier: "you.debug", action: actions.onOpenDebug)
                        }
                    }
                }
                if state.isSampleData { DemoDataBadge() }
                Text("Version \(state.versionText)").font(.footnote).foregroundStyle(.secondary)
            }
            .padding(Theme.Spacing.l)
        }
        .navigationTitle("You")
    }

    private func profileCard(_ profile: YouViewState.Profile) -> some View {
        GlassCard {
            HStack(spacing: Theme.Spacing.l) {
                Text(profile.emoji).font(.system(size: 44)).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    Text(profile.name).font(.title3.bold())
                    Text(profile.detail).font(.subheadline).foregroundStyle(.secondary)
                    Text("Pay \(Money.format(profile.annualIncome)) a year. Savings \(Money.format(profile.savings)). \(profile.housingText).")
                        .font(.footnote)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }

    private var factsCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                Text("About your money").font(.headline)
                ForEach(state.personalFacts, id: \.self) { Text($0).font(.subheadline) }
            }
        }
    }

    private func row(title: String, detail: String?, systemImage: String, identifier: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.m) {
                Image(systemName: systemImage).frame(width: 28).accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.body)
                    if let detail { Text(detail).font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.leading) }
                }
                Spacer()
                Image(systemName: "chevron.right").font(.footnote).foregroundStyle(.tertiary).accessibilityHidden(true)
            }
            .frame(minHeight: Theme.minTarget)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(detail.map { "\(title). \($0)" } ?? title)
        .accessibilityIdentifier(identifier)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") { YouView(state: Fixtures.You.ready).previewInNavigation() }
#Preview("Ready · dark") { YouView(state: Fixtures.You.ready).previewInNavigation().previewDark() }
#Preview("Ready · AX3") { YouView(state: Fixtures.You.ready).previewInNavigation().previewLargeType() }
#Preview("Release · light") { YouView(state: Fixtures.You.release).previewInNavigation() }
#Preview("Loading · light") { YouView(state: Fixtures.You.loading).previewInNavigation() }
#Preview("Error · light") { YouView(state: Fixtures.You.error).previewInNavigation() }
