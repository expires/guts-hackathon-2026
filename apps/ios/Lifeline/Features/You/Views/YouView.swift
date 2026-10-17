// Rebuilt for ADR 0026 (You-Profile.dc.html) by W7.
import SwiftUI

/// You tab: profile, best scores, bank and data sources, settings, credits.
struct YouView: View {
    let state: YouViewState
    var actions: YouActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                switch state.profilePhase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    header
                }
                scores
                if !state.personalFacts.isEmpty { facts }
                bankAndData
                settings
                if !state.credits.isEmpty {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        ForEach(state.credits, id: \.self) {
                            Text($0).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                        Text("Version \(state.versionText) · \(state.clientText) data")
                            .font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("you.credits")
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    @ViewBuilder
    private var header: some View {
        if let profile = state.profile {
            HStack(spacing: Theme.Spacing.m) {
                LLIconImage(LLIcon.face(emoji: profile.emoji), size: 48)
                    .frame(width: 56, height: 56)
                    .inkSurface(HandCut((18, 22, 17, 21), (21, 17, 22, 18)), fill: Theme.Palette.work)
                VStack(alignment: .leading, spacing: 2) {
                    Text(profile.name).font(.llTitle).accessibilityAddTraits(.isHeader)
                    Text(state.personaLine).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if state.isSampleData { DemoDataBadge() }
            }
            .accessibilityIdentifier("you.profile")
        }
    }

    private var scores: some View {
        HStack(spacing: Theme.Spacing.s) {
            score(icon: .trophy, value: state.bestIndexText, label: "Best INDEX")
            score(icon: .ribbon, value: state.ribbonsText, label: "Ribbons")
            score(icon: .lesson, value: state.conceptsText, label: "Concepts")
        }
    }

    private func score(icon: LLIcon, value: String, label: String) -> some View {
        VStack(spacing: 2) {
            LLIconImage(icon, size: 24)
            Text(value).font(.llTitle).lineLimit(1).minimumScaleFactor(0.6)
            Text(label).font(.llLabel).foregroundStyle(Theme.Palette.muted).lineLimit(1).minimumScaleFactor(0.8)
        }
        .padding(.vertical, Theme.Spacing.m)
        .padding(.horizontal, Theme.Spacing.xs)
        .frame(maxWidth: .infinity)
        .inkSurface(.card)
        .accessibilityElement(children: .combine)
    }

    private var facts: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            ForEach(state.personalFacts, id: \.self) { fact in
                HStack(alignment: .top, spacing: Theme.Spacing.s) {
                    LLIconImage(.why, size: 24)
                    Text(fact).font(.llBody).fixedSize(horizontal: false, vertical: true)
                }
            }
        }
    }

    private var bankAndData: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            BlockTitle(text: "Bank and data")
            VStack(spacing: 0) {
                HStack(spacing: Theme.Spacing.m) {
                    LLIconImage(.bank, size: 32)
                    VStack(alignment: .leading, spacing: 0) {
                        Text(state.bankName).font(.llBodyBold)
                        Text(state.bankDetail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    Button(action: actions.onConnectBank) { Text("Accounts").font(.llLabelBold).lineLimit(1) }
                        .buttonStyle(.plain)
                        .padding(.horizontal, Theme.Spacing.m)
                        .frame(minHeight: Theme.minTarget)
                        .inkSurface(.badge, lineWidth: Theme.chipOutline)
                        .accessibilityLabel("Accounts. Connect Monzo or Trading212")
                        .accessibilityIdentifier("you.accounts")
                }
                .padding(.horizontal, Theme.Spacing.l)
                .padding(.vertical, Theme.Spacing.m)
                ForEach(state.dataRows) { row in
                    RuleDivider()
                    HStack(spacing: Theme.Spacing.s) {
                        LLIconImage(Theme.icon(for: row.status), size: 24)
                        Text(row.name).font(.llBody).lineLimit(1).minimumScaleFactor(0.8)
                        Spacer(minLength: Theme.Spacing.s)
                        Text(row.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted).lineLimit(1)
                    }
                    .padding(.horizontal, Theme.Spacing.l)
                    .frame(minHeight: Theme.minTarget)
                    .accessibilityElement(children: .combine)
                }
                RuleDivider()
                row(icon: .why, title: "Where our data comes from", id: "you.sources", action: actions.onOpenSources)
            }
            .inkSurface(.cardAlt)
        }
    }

    private var settings: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            BlockTitle(text: "Settings")
            VStack(spacing: 0) {
                row(icon: .lock, title: "Lifeline Plus", id: "you.store", action: actions.onOpenStore)
                RuleDivider()
                row(icon: .check, title: "Your plan", id: "you.plan", action: actions.onOpenPlan)
                RuleDivider()
                row(icon: .test, title: "How good is the advice?", id: "you.evaluation", action: actions.onOpenEvaluation)
                RuleDivider()
                row(icon: .investment, title: "How good is the spend guess?", id: "you.spendAccuracy", action: actions.onOpenSpendAccuracy)
                if state.showsDebugMenu {
                    RuleDivider()
                    row(icon: .statusCached, title: "Debug menu", id: "you.debug", action: actions.onOpenDebug)
                }
            }
            .inkSurface(.card)
        }
    }

    private func row(icon: LLIcon, title: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.m) {
                LLIconImage(icon, size: 24)
                Text(title).font(.llBody).lineLimit(1).minimumScaleFactor(0.8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Chevron()
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.l)
            .frame(minHeight: 52)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(id)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") { YouView(state: YouFixturesW7.full).previewInNavigation() }
#Preview("Ready · dark") { YouView(state: YouFixturesW7.full).previewInNavigation().previewDark() }
#Preview("Ready · AX3") { YouView(state: YouFixturesW7.full).previewInNavigation().previewLargeType() }
#Preview("Release · light") { YouView(state: Fixtures.You.release).previewInNavigation() }
#Preview("Loading · light") { YouView(state: Fixtures.You.loading).previewInNavigation() }
#Preview("Error · light") { YouView(state: Fixtures.You.error).previewInNavigation() }
