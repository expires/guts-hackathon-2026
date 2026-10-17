import SwiftUI

/// Onboarding (ADR 0029): welcome, sign in, connect your money, importing, Next Move reveal, 3 tips.
/// Design system only: paper, ink outlines, own buttons and fields.
struct OnboardingView: View {
    let state: OnboardingViewState
    var actions: OnboardingActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Group {
            switch state.step {
            case let .welcome(page): welcome(page)
            case .signIn: signIn
            case .connect: connect
            case .samples: samples
            case .manual: OnboardingManualView(manual: state.manual, isBusy: state.isBusy, errorMessage: state.errorMessage, actions: actions)
            case .importing: importing
            case .reveal: reveal
            case .tips: tips
            }
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: state.step)
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    // MARK: Shared layout

    /// Scrolling content with the buttons pinned above the home indicator.
    private func page(
        @ViewBuilder content: () -> some View,
        @ViewBuilder buttons: () -> some View
    ) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                content()
                if let message = state.errorMessage { OnboardingErrorCard(message: message, onDismiss: actions.onDismissError) }
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xxl)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .scrollBounceBehavior(.basedOnSize)
        .safeAreaInset(edge: .bottom, spacing: 0) {
            VStack(spacing: Theme.Spacing.s) { buttons() }
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.vertical, Theme.Spacing.m)
                .background(Theme.Palette.paper.ignoresSafeArea(edges: .bottom))
        }
    }

    private func header(_ title: String, back: Bool) -> some View {
        ScreenHeader(
            title: title,
            leading: back ? HeaderSquareButton(kind: .back, identifier: "onboarding.back", action: actions.onBack) : nil
        ) {
            if state.isSampleData { DemoDataBadge() }
        }
    }

    // MARK: Welcome

    private func welcome(_ index: Int) -> some View {
        let item = state.pages[min(max(0, index), state.pages.count - 1)]
        return page {
            HStack {
                if index > 0 {
                    HeaderSquareButton(kind: .back, identifier: "onboarding.back", action: actions.onBack)
                }
                Spacer()
                Button("Skip", action: actions.onSkipWelcome)
                    .buttonStyle(.text)
                    .frame(minWidth: Theme.minTarget, minHeight: Theme.minTarget)
                    .contentShape(.rect)
                    .accessibilityIdentifier("onboarding.skip")
            }
            .frame(minHeight: Theme.minTarget)
            VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
                art(item.art)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Spacing.xl)
                Text(item.title)
                    .font(.llHero)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)
                    .accessibilityIdentifier("onboarding.welcome.title")
                Text(item.text).font(.llBody).fixedSize(horizontal: false, vertical: true)
                PageDots(count: state.pages.count, current: index)
            }
        } buttons: {
            Button(index + 1 < state.pages.count ? "Next" : "Get started", action: actions.onNext)
                .buttonStyle(.main)
                .accessibilityIdentifier("onboarding.next")
        }
    }

    @ViewBuilder
    private func art(_ art: OnboardingViewState.WelcomePage.Art) -> some View {
        switch art {
        case .penny: PennyView(mood: .happy, size: 140)
        case .why: LLIconImage(.why, size: 120).padding(Theme.Spacing.xl).inkSurface(.hero, hero: true)
        case .test: LLIconImage(.test, size: 120).padding(Theme.Spacing.xl).inkSurface(.cardAlt, fill: Theme.Palette.money, hero: true)
        }
    }

    // MARK: Sign in

    private var signIn: some View {
        page {
            header("Save your progress", back: true)
            HStack(alignment: .top, spacing: Theme.Spacing.m) {
                PennyView(mood: .smiling, size: 64)
                Text("Sign in so your money, your plan and your lives stay with you.")
                    .font(.llBody)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if !state.signIn.appleAvailable {
                Text("Sign in with Apple is not set up in this build. Continue with a demo account on this phone.")
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                    .accessibilityIdentifier("onboarding.appleUnavailable")
            }
        } buttons: {
            if state.signIn.appleAvailable {
                PrimaryButton(title: "Sign in with Apple", isBusy: state.isBusy, action: actions.onSignInWithApple)
                    .disabled(state.isBusy)
                    .accessibilityIdentifier("onboarding.apple")
                Button("Continue without an account", action: actions.onContinueWithoutAccount)
                    .buttonStyle(.second)
                    .accessibilityIdentifier("onboarding.demo")
            } else {
                Button("Continue", action: actions.onContinueWithoutAccount)
                    .buttonStyle(.main)
                    .accessibilityIdentifier("onboarding.demo")
            }
        }
    }

    // MARK: Connect

    private var connect: some View {
        page {
            header("Connect your money", back: true)
            if let note = state.signIn.note {
                Text(note).font(.llLabel).foregroundStyle(Theme.Palette.muted).accessibilityIdentifier("onboarding.signInNote")
            }
            Text("Pick one. Your Next Move uses only these numbers.")
                .font(.llBody)
                .fixedSize(horizontal: false, vertical: true)
            VStack(spacing: 0) {
                ForEach(Array(state.options.enumerated()), id: \.element.id) { offset, option in
                    if offset > 0 { RuleDivider() }
                    Button { actions.onConnect(option.kind) } label: {
                        HStack(spacing: Theme.Spacing.m) {
                            LLIconImage(icon(for: option.kind), size: 32)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(option.title).font(.llBodyBold)
                                Text(option.subtitle).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            Spacer(minLength: 0)
                            if option.isUnavailable {
                                Chip(text: "Unavailable", fill: Theme.Palette.other)
                            } else {
                                Chevron()
                            }
                        }
                        .foregroundStyle(Theme.Palette.ink)
                        .padding(.horizontal, Theme.Spacing.l)
                        .padding(.vertical, Theme.Spacing.m)
                        .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
                        .contentShape(.rect)
                    }
                    .buttonStyle(.plain)
                    .disabled(state.isBusy)
                    .opacity(option.isUnavailable ? 0.6 : 1)
                    .accessibilityLabel([option.title, option.subtitle, option.isUnavailable ? "Unavailable" : nil].compactMap { $0 }.joined(separator: ". "))
                    .accessibilityIdentifier("onboarding.option.\(option.kind.rawValue)")
                }
            }
            .inkSurface(.card)
            if state.isBusy {
                LoadingStateView(state: .standard)
            }
        } buttons: {
            EmptyView()
        }
    }

    private func icon(for kind: OnboardingViewState.ConnectOption.Kind) -> LLIcon {
        switch kind {
        case .sample: .study
        case .monzo: .bank
        case .trading212: .investment
        case .statement: .bills
        case .manual: .budget
        }
    }

    // MARK: Sample students

    private var samples: some View {
        page {
            header("Pick a student", back: true)
            Text("Each is a made-up student with 3 months of payments. Your Next Move is worked out from it, live.")
                .font(.llBody)
                .fixedSize(horizontal: false, vertical: true)
            if state.samplesLoading && state.samples.isEmpty {
                LoadingStateView(state: .standard)
            }
            ForEach(Array(state.samples.enumerated()), id: \.element.id) { offset, sample in
                Button { actions.onPickSample(sample.id) } label: {
                    HStack(alignment: .top, spacing: Theme.Spacing.m) {
                        LLIconImage(.study, size: 40)
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            Text(sample.title).font(.llBodyBold)
                            Text(sample.text).font(.llLabel).fixedSize(horizontal: false, vertical: true)
                            Text(sample.fundingText).font(.llLabelBold).foregroundStyle(Theme.Palette.muted)
                                .fixedSize(horizontal: false, vertical: true)
                            Text(sample.monthsText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        Chevron()
                    }
                    .foregroundStyle(Theme.Palette.ink)
                    .padding(Theme.Spacing.l)
                    .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
                    .inkSurface(offset.isMultiple(of: 2) ? .card : .cardAlt)
                    .contentShape(.rect)
                }
                .buttonStyle(.plain)
                .accessibilityElement(children: .combine)
                .accessibilityAddTraits(.isButton)
                .accessibilityIdentifier("onboarding.sample.\(sample.id)")
            }
        } buttons: {
            EmptyView()
        }
    }

    // MARK: Importing

    private var importing: some View {
        page {
            header(state.importing.title, back: false)
            HStack(spacing: Theme.Spacing.m) {
                PennyView(mood: state.importing.isFinished ? .happy : .thinking, size: 64)
                Text(state.importing.isFinished ? "Done. Here is your next move." : "This takes a few seconds.")
                    .font(.llBody)
            }
            VStack(alignment: .leading, spacing: 0) {
                ForEach(Array(state.importing.stages.prefix(max(state.importing.shownCount, 0)).enumerated()), id: \.element.id) { offset, stage in
                    if offset > 0 { RuleDivider() }
                    HStack(spacing: Theme.Spacing.m) {
                        if stage.done {
                            LLIconImage(.check, size: 28)
                        } else {
                            ProgressView().tint(Theme.Palette.ink).frame(width: 28, height: 28)
                        }
                        Text(stage.label).font(stage.done ? .llBodyBold : .llBody)
                        Spacer(minLength: 0)
                    }
                    .padding(.horizontal, Theme.Spacing.l)
                    .frame(minHeight: Theme.minTarget + 8)
                    .transition(.opacity.combined(with: .move(edge: .bottom)))
                    .accessibilityElement(children: .combine)
                    .accessibilityValue(stage.done ? "Done" : "In progress")
                    .accessibilityIdentifier("onboarding.stage.\(stage.id)")
                }
            }
            .inkSurface(.card)
            .animation(Motion.standard(reduceMotion: reduceMotion), value: state.importing)
            if let summary = state.importing.summary {
                Text(summary).font(.llBodyBold).accessibilityIdentifier("onboarding.importSummary")
            }
            ForEach(state.importing.warnings, id: \.self) { warning in
                Label(warning, icon: .why).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        } buttons: {
            EmptyView()
        }
    }

    // MARK: Reveal

    private var reveal: some View {
        page {
            header("Your next move", back: false)
            if let reveal = state.reveal {
                VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                    Text("Your next money move").llEyebrow()
                    Text(reveal.action)
                        .font(.llTitle)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("onboarding.reveal.action")
                    Text(reveal.headline).font(.llBody).fixedSize(horizontal: false, vertical: true)
                    RuleDivider()
                    Text(reveal.impactAmountText)
                        .font(.llHero)
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                        .accessibilityIdentifier("onboarding.reveal.impact")
                    Text(reveal.impactCaption).font(.llLabel)
                    HStack(spacing: Theme.Spacing.m) {
                        Text(reveal.confidenceWord).font(.llBodyBold)
                        ConfidenceMeter(filled: reveal.confidenceFilled)
                    }
                    Text(reveal.confidenceLabel).font(.llLabel).fixedSize(horizontal: false, vertical: true)
                }
                .padding(18)
                .frame(maxWidth: .infinity, alignment: .leading)
                .foregroundStyle(Theme.Palette.ink)
                .inkSurface(.hero, hero: true)
                .overlay(alignment: .topTrailing) {
                    PennyView(mood: .happy, size: 56).rotationEffect(.degrees(8)).offset(x: -14, y: -28).accessibilityHidden(true)
                }
                .padding(.top, Theme.Spacing.s)
                .accessibilityElement(children: .contain)
                .accessibilityIdentifier("onboarding.reveal")
            } else {
                Text("No move right now. Your money looks fine.").font(.llBody)
            }
        } buttons: {
            Button("Continue", action: actions.onNext)
                .buttonStyle(.main)
                .accessibilityIdentifier("onboarding.next")
        }
    }

    // MARK: Tips

    private var tips: some View {
        page {
            header(state.tips.count == 1 ? "1 thing about your money" : "\(state.tips.count) things about your money", back: false)
            ForEach(state.tips) { tip in
                HStack(alignment: .top, spacing: Theme.Spacing.m) {
                    Text("\(tip.number)")
                        .font(.llTitle)
                        .frame(width: 44, height: 44)
                        .inkSurface(.badge, fill: Theme.Palette.money)
                        .foregroundStyle(Theme.Palette.onArea)
                        .accessibilityHidden(true)
                    Text(tip.text).font(.llBody).fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
                .padding(Theme.Spacing.l)
                .frame(maxWidth: .infinity, alignment: .leading)
                .inkSurface(tip.number.isMultiple(of: 2) ? .cardAlt : .card)
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("onboarding.tip.\(tip.number)")
            }
        } buttons: {
            Button("Start", action: actions.onFinish)
                .buttonStyle(.main)
                .accessibilityIdentifier("onboarding.finish")
        }
    }
}

/// Three hand-cut dots, the current one ink-filled.
private struct PageDots: View {
    let count: Int
    let current: Int

    var body: some View {
        HStack(spacing: Theme.Spacing.s) {
            ForEach(0..<count, id: \.self) { index in
                HandCut((5, 4, 6, 3))
                    .fill(index == current ? Theme.Palette.ink : Theme.Palette.surface)
                    .overlay(HandCut((5, 4, 6, 3)).strokeBorder(Theme.Palette.ink, lineWidth: 2))
                    .frame(width: index == current ? 28 : 12, height: 12)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Page \(current + 1) of \(count)")
    }
}

/// Error for the current step, with a close button.
struct OnboardingErrorCard: View {
    let message: String
    let onDismiss: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            Text(message)
                .font(.llBody)
                .foregroundStyle(Theme.Palette.onArea)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
            HeaderSquareButton(kind: .close, identifier: "onboarding.error.close", action: onDismiss)
        }
        .padding(Theme.Spacing.l)
        .inkSurface(.cardAlt, fill: Theme.Palette.health)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("onboarding.error")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Welcome · light") { OnboardingView(state: OnboardingFixtures.welcome) }
#Preview("Welcome · dark") { OnboardingView(state: OnboardingFixtures.welcome).previewDark() }
#Preview("Welcome · AX3") { OnboardingView(state: OnboardingFixtures.welcome).previewLargeType() }
#Preview("Sign in · light") { OnboardingView(state: OnboardingFixtures.signInDemoOnly) }
#Preview("Connect · light") { OnboardingView(state: OnboardingFixtures.connect) }
#Preview("Connect, error · dark") { OnboardingView(state: OnboardingFixtures.connectError).previewDark() }
#Preview("Samples · light") { OnboardingView(state: OnboardingFixtures.samples) }
#Preview("Samples · dark") { OnboardingView(state: OnboardingFixtures.samples).previewDark() }
#Preview("Samples · AX3") { OnboardingView(state: OnboardingFixtures.samples).previewLargeType() }
#Preview("Importing · light") { OnboardingView(state: OnboardingFixtures.importing) }
#Preview("Importing · AX3") { OnboardingView(state: OnboardingFixtures.importing).previewLargeType() }
#Preview("Reveal · light") { OnboardingView(state: OnboardingFixtures.reveal) }
#Preview("Reveal · dark") { OnboardingView(state: OnboardingFixtures.reveal).previewDark() }
#Preview("Tips · light") { OnboardingView(state: OnboardingFixtures.tips) }
#Preview("Tips · AX3") { OnboardingView(state: OnboardingFixtures.tips).previewLargeType() }
