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
                if let habits = state.habits { habitCard(habits) }
                scores
                if !state.personalFacts.isEmpty { facts }
                bankAndData
                settings
                judgeMode
                if !state.credits.isEmpty {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        ForEach(state.credits, id: \.self) {
                            Text($0).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                        Text(L10n.tr("Version \(state.versionText)"))
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
        .refreshable { await actions.onRefresh() }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    @ViewBuilder
    private var header: some View {
        if let profile = state.profile {
            Button(action: actions.onOpenAccount) {
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
                Chevron()
            }
            .foregroundStyle(Theme.Palette.ink)
            .frame(minHeight: Theme.minTarget)
            .contentShape(.rect)
            }
            .buttonStyle(.plain)
            .accessibilityHint("Opens your account: sign out, reset or delete")
            .accessibilityIdentifier("you.profile")
        }
    }

    /// Habit score (ADR 0066): overall 0-100 and six ratios as bars. No amounts.
    private func habitCard(_ card: HabitCard) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            HStack(alignment: .firstTextBaseline) {
                Text("Money habits").font(.llBodyBold)
                Spacer()
                if let overall = card.overall {
                    Text("\(overall)").font(.llHero).contentTransition(.numericText(value: Double(overall)))
                    Text("/ 100").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
            }
            ForEach(card.rows) { row in
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    HStack {
                        Text(row.name).font(.llLabel)
                        Spacer()
                        Text("\(row.value)").font(.llLabelBold)
                    }
                    InkProgressBar(value: Double(row.value) / 100, height: 12)
                }
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(Text(row.name))
                .accessibilityValue("\(row.value) out of 100")
            }
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.card)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("you.habits")
    }

    /// "Lessons 3/48" (PENNY_V3_BUILD E5). Tapping it opens Learn.
    private var scores: some View {
        Button(action: actions.onOpenLearn) {
            HStack(spacing: Theme.Spacing.m) {
                LLIconImage(.lesson, size: 32)
                VStack(alignment: .leading, spacing: 0) {
                    Text("Lessons").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    Text(state.lessonsText).font(.llTitle).lineLimit(1).minimumScaleFactor(0.6)
                        .contentTransition(.numericText())
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Chevron()
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.l)
            .padding(.vertical, Theme.Spacing.m)
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
            .inkSurface(.card)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(L10n.tr("Lessons \(state.lessonsText)"))
        .accessibilityHint(L10n.tr("Opens Learn"))
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier("you.lessons")
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
            BlockTitle(text: "Your money and data")
            if !state.honestyText.isEmpty {
                Text(state.honestyText)
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("you.honesty")
            }
            VStack(spacing: 0) {
                connectMoneyRow
                RuleDivider()
                row(icon: .tabYou, title: "Your profile", id: "you.profile", action: actions.onOpenProfile)
                ForEach(state.dataRows) { row in
                    RuleDivider()
                    HStack(spacing: Theme.Spacing.s) {
                        LLIconImage(Theme.icon(for: row.status), size: 24)
                        Text(row.name).font(.llBody).lineLimit(2).minimumScaleFactor(0.8)
                            .fixedSize(horizontal: false, vertical: true)
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
                row(icon: .why, title: "Ask Penny", id: "you.askPenny", action: actions.onAskPenny)
                RuleDivider()
                row(icon: .travel, title: "Change language", id: "you.changeLanguage", action: actions.onChangeLanguage)
                RuleDivider()
                row(icon: .lesson, title: L10n.tr("How \(Brand.productName) uses AI"), id: "you.aiDisclosure", action: actions.onOpenAIDisclosure)
                RuleDivider()
                if let buffer = state.buffer {
                    bufferRow(buffer)
                    RuleDivider()
                }
                // Cut (PENNY_V3_BUILD B4, F1): the plan, the advice check and the spend guess check.
                if state.showsCutFeatures {
                    row(icon: .check, title: "Your plan", id: "you.plan", action: actions.onOpenPlan)
                    RuleDivider()
                    if state.showsEvaluation {
                        row(icon: .test, title: "How good is the advice?", id: "you.evaluation", action: actions.onOpenEvaluation)
                        RuleDivider()
                    }
                    row(icon: .investment, title: "How good is the spend guess?", id: "you.spendAccuracy", action: actions.onOpenSpendAccuracy)
                    RuleDivider()
                }
                if state.showsDebugMenu {
                    RuleDivider()
                    row(icon: .statusCached, title: "Debug menu", id: "you.debug", action: actions.onOpenDebug)
                    RuleDivider()
                }
                versionRow
            }
            .inkSurface(.card)
        }
    }

    /// "Safety buffer" (PENNY_V3_BUILD B2): 0, 5, 10, 15 or 20% kept back from what you can spend.
    private func bufferRow(_ buffer: YouViewState.BufferSetting) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            HStack(spacing: Theme.Spacing.m) {
                LLIconImage(.savings, size: 24)
                VStack(alignment: .leading, spacing: 0) {
                    Text("Safety buffer").font(.llBody)
                    Text("Kept back before your weekly amount").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if buffer.isSaving { ProgressView().accessibilityLabel(L10n.tr("Saving")) }
            }
            HStack(spacing: Theme.Spacing.xs) {
                ForEach(buffer.options, id: \.self) { pct in
                    let isOn = pct == buffer.selected
                    Button { actions.onSetBuffer(pct) } label: {
                        Text("\(pct)%")
                            .font(.llLabelBold)
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                            .foregroundStyle(isOn ? Theme.Palette.surface : Theme.Palette.ink)
                            .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                            .inkSurface(.chip, fill: isOn ? Theme.Palette.ink : Theme.Palette.surface, lineWidth: Theme.chipOutline)
                            .contentShape(.rect)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(L10n.tr("Safety buffer \(pct) percent"))
                    .accessibilityAddTraits(isOn ? [.isSelected, .isButton] : .isButton)
                    .accessibilityIdentifier("you.buffer.\(pct)")
                }
            }
            if let error = buffer.errorText {
                Text(error).font(.llLabelBold).foregroundStyle(Theme.Palette.health)
                    .accessibilityIdentifier("you.buffer.error")
            }
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, Theme.Spacing.m)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("you.buffer")
    }

    /// Judge mode (DIRECTION_V2 section 4): "New player" and "Reset demo".
    private var judgeMode: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            BlockTitle(text: "Judge mode")
            VStack(spacing: 0) {
                row(icon: .faceBaby, title: "New player", id: "you.newPlayer", action: actions.onNewPlayer)
                RuleDivider()
                row(icon: .rewind, title: "Reset demo", id: "you.resetDemo", action: actions.onResetDemo)
            }
            .inkSurface(.cardAlt)
        }
    }

    /// "Connect your money": always visible. Shows how the money data got in.
    private var connectMoneyRow: some View {
        Button(action: actions.onConnectMoney) {
            HStack(spacing: Theme.Spacing.m) {
                LLIconImage(.savings, size: 32)
                VStack(alignment: .leading, spacing: 0) {
                    Text("Connect your money").font(.llBodyBold)
                    Text(state.connectMoneyText ?? "Checking…").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Chevron()
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.l)
            .padding(.vertical, Theme.Spacing.m)
            .frame(minHeight: 52)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("you.connectMoney")
    }

    /// "Version": app name, version and checkpoint, build time, features. Not a button.
    private var versionRow: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            LLIconImage(.age, size: 24)
            VStack(alignment: .leading, spacing: 2) {
                Text("Version").font(.llBody)
                Text(state.buildInfo.title).font(.llLabelBold)
                ForEach(state.buildInfo.detailLines, id: \.self) { line in
                    Text(line).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, Theme.Spacing.m)
        .frame(minHeight: 52)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("you.version")
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
