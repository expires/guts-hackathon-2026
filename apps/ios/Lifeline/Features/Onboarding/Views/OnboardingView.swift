import Charts
import SwiftUI

/// Onboarding (ADR 0069): Welcome, Problem, Language, What you can do, (Try Penny in the glue), Pick your student,
/// Building their profile, Their profile, How Penny decides, Their Next Move, Start.
/// Design system only: paper, ink outlines, own buttons and fields.
struct OnboardingView: View {
    let state: OnboardingViewState
    var actions: OnboardingActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        Group {
            switch state.step {
            case .welcome: welcome
            case .problem: problem
            case .language: language
            case .features: features
            case .penny: EmptyView() // The glue shows the Penny chat (it needs the client).
            case .signIn: signIn
            case .connect: connect
            case .manual: OnboardingManualView(manual: state.manual, isBusy: state.isBusy, errorMessage: state.errorMessage, actions: actions)
            case .building: building
            case .profile: profile
            case .howDecides: howDecides
            case .nextMove: nextMove
            }
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: state.step)
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
        .sheet(isPresented: Binding(
            get: { state.trading212.isPresented },
            set: { if !$0 { actions.onCloseTrading212() } }
        )) {
            Trading212SheetView(sheet: state.trading212, onSubmit: actions.onSubmitTrading212, onClose: actions.onCloseTrading212)
                .presentationDetents([.large])
        }
    }

    // MARK: Shared layout

    /// Scrolling content with the buttons pinned above the home indicator.
    private func page(
        showsButtons: Bool = true,
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
            // No buttons: no bar. An empty bar drew a small paper rectangle over the list.
            if showsButtons {
                VStack(spacing: Theme.Spacing.s) { buttons() }
                    .frame(maxWidth: .infinity)
                    .padding(.horizontal, Theme.Spacing.margin)
                    .padding(.vertical, Theme.Spacing.m)
                    .background(Theme.Palette.paper.ignoresSafeArea(edges: .bottom))
            }
        }
    }

    private var backButton: HeaderSquareButton {
        HeaderSquareButton(kind: .back, identifier: "onboarding.back", action: actions.onBack)
    }

    /// Back, title, then Skip where it makes sense. No sample data badge (B4): "Pick your student" says it once.
    private func header(_ title: String, skip: Bool = false) -> some View {
        ScreenHeader(title: title, leading: backButton) {
            if skip { skipButton }
        }
    }

    private var skipButton: some View {
        Button("Skip", action: actions.onSkip)
            .buttonStyle(.text)
            .frame(minWidth: Theme.minTarget, minHeight: Theme.minTarget)
            .contentShape(.rect)
            .accessibilityIdentifier("onboarding.skip")
    }

    private func nextButton(_ title: LocalizedStringKey, identifier: String = "onboarding.next") -> some View {
        Button(title, action: actions.onNext)
            .buttonStyle(.main)
            .accessibilityIdentifier(identifier)
    }

    private func section(_ title: LocalizedStringKey) -> some View {
        Text(title).font(.llSection).accessibilityAddTraits(.isHeader)
    }

    // MARK: Welcome

    private var welcome: some View {
        page {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                PennyView(mood: .happy, size: 170)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Spacing.m)
                    .accessibilityHidden(true)
                Text(L10n.tr("Your student money, sorted."))
                    .font(.llHero)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)
                    .accessibilityIdentifier("onboarding.welcome.title")
                VStack(alignment: .leading, spacing: 0) {
                    welcomeLine(.study, L10n.tr("For UK students and graduates."), id: "who")
                    RuleDivider()
                    welcomeLine(.bank, L10n.tr("Penny uses your statement and live UK data."), id: "what")
                    RuleDivider()
                    welcomeLine(.check, L10n.tr("You get one clear answer each month, with the evidence."), id: "get")
                }
                .inkSurface(.card)
            }
            // Fills the screen: the content sits in the middle of the space above the button (C1). Large text
            // scrolls instead.
            .modifier(FillScreenHeight(isOn: !typeSize.isAccessibilitySize))
        } buttons: {
            nextButton("Get started")
        }
    }

    private func welcomeLine(_ icon: LLIcon, _ text: String, id: String) -> some View {
        HStack(alignment: .center, spacing: Theme.Spacing.m) {
            LLIconImage(icon, size: 32)
            Text(text).font(.llBodyBold).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, Theme.Spacing.m)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("onboarding.welcome.\(id)")
    }

    // MARK: Problem

    private var problem: some View {
        page {
            HStack { backButton; Spacer() }
            Text("One app. Every source. One clear decision.")
                .font(.llHero)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
                .accessibilityIdentifier("onboarding.problem.title")
            Text(L10n.tr("Your loan, job, bank and bills each tell you something different. Penny puts them with live UK data and gives you one clear answer."))
                .font(.llBody)
                .fixedSize(horizontal: false, vertical: true)
            ProblemArt()
        } buttons: {
            nextButton("Continue")
        }
    }

    // MARK: Language

    private var language: some View {
        LanguagePickerView(
            selection: state.language,
            onPick: actions.onPickLanguage,
            onConfirm: actions.onConfirmLanguage,
            onBack: actions.onBack,
            onSkip: actions.onSkip
        )
    }

    // MARK: What you can do

    private var features: some View {
        page {
            ScreenHeader(title: L10n.tr("What you can do"), leading: backButton)
            // Explainer list: icon, headline, one line. No chevrons: nothing here is a button.
            VStack(alignment: .leading, spacing: 0) {
                ForEach(Array(OnboardingViewState.featureRows.enumerated()), id: \.element.id) { offset, row in
                    if offset > 0 { RuleDivider() }
                    HStack(alignment: .center, spacing: Theme.Spacing.m) {
                        LLIconImage(featureIcon(row.id), size: 36)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(row.title).font(.llBodyBold).fixedSize(horizontal: false, vertical: true)
                            Text(row.text).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Spacer(minLength: 0)
                    }
                    .padding(.horizontal, Theme.Spacing.l)
                    .padding(.vertical, Theme.Spacing.m)
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("onboarding.feature.\(row.id)")
                }
            }
            .inkSurface(.card)
        } buttons: {
            nextButton("Continue")
        }
    }

    private func featureIcon(_ id: String) -> LLIcon {
        switch id {
        case "allMoney": .bank
        case "weekly": .budget
        case "maths": .why
        case "penny": .pennySmiling
        default: .trophy
        }
    }

    // MARK: Sign in (not in the ADR 0069 order; kept for a later build)

    private var signIn: some View {
        page {
            ScreenHeader(title: L10n.tr("Save your progress"), leading: backButton)
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
                PrimaryButton(title: L10n.tr("Sign in with Apple"), isBusy: state.isBusy, action: actions.onSignInWithApple)
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

    // MARK: Pick your student

    private var connect: some View {
        page(showsButtons: false) {
            header(L10n.tr("Pick your student"))
            if let note = state.signIn.note {
                Text(note).font(.llLabel).foregroundStyle(Theme.Palette.muted).accessibilityIdentifier("onboarding.signInNote")
            }
            Text(L10n.tr("Pick one to see how Penny works. Their forecast is worked out live from their statement."))
                .font(.llBody)
                .fixedSize(horizontal: false, vertical: true)
            if state.samplesLoading && state.samples.isEmpty {
                SkeletonCard(lines: 6)
                SkeletonCard(lines: 6)
            }
            ForEach(state.samples) { sample in
                StudentCard(sample: sample, onPick: { actions.onPickSample(sample.id) })
            }
            if !state.samples.isEmpty {
                HonestyLine()
            }
            section("Or use your own money")
            if let notice = state.monzoNotice {
                HStack(spacing: Theme.Spacing.m) {
                    ProgressView()
                    Text(notice).font(.llBody).fixedSize(horizontal: false, vertical: true)
                }
                .padding(Theme.Spacing.l)
                .frame(maxWidth: .infinity, alignment: .leading)
                .inkSurface(.cardAlt)
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("onboarding.monzo.waiting")
            }
            VStack(spacing: 0) {
                ForEach(Array(state.options.enumerated()), id: \.element.id) { offset, option in
                    if offset > 0 { RuleDivider() }
                    Button { actions.onConnect(option.kind) } label: {
                        HStack(spacing: Theme.Spacing.m) {
                            LLIconImage(option.kind == .manual ? .budget : .bills, size: 32)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(option.title).font(.llBodyBold)
                                Text(option.subtitle).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            Spacer(minLength: 0)
                            if option.isUnavailable {
                                Chip(text: L10n.tr("Unavailable"), fill: Theme.Palette.other)
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
                    .accessibilityLabel([option.title, option.subtitle].joined(separator: ". "))
                    .accessibilityIdentifier("onboarding.option.\(option.kind.rawValue)")
                }
            }
            .inkSurface(.card)
        } buttons: {
            EmptyView()
        }
    }

    // MARK: Building their profile

    private var building: some View {
        page(showsButtons: state.building.isFinished) {
            header(L10n.tr("Building their profile"))
            HStack(spacing: Theme.Spacing.m) {
                PennyView(mood: state.building.isFinished ? .happy : .thinking, size: 56)
                Text(state.building.isFinished ? "Done. Their profile is ready." : "Each step finishes when its data is in.")
                    .font(.llBody)
                    .fixedSize(horizontal: false, vertical: true)
            }
            VStack(alignment: .leading, spacing: 0) {
                ForEach(Array(state.building.stages.enumerated()), id: \.element.id) { offset, stage in
                    if offset > 0 { RuleDivider() }
                    BuildStageRow(stage: stage)
                }
            }
            .inkSurface(.card)
            .animation(Motion.standard(reduceMotion: reduceMotion), value: state.building)
        } buttons: {
            if state.building.isFinished {
                nextButton("View profile", identifier: "onboarding.viewProfile")
            }
        }
    }

    // MARK: Their profile

    @ViewBuilder
    private var profile: some View {
        page {
            header(L10n.tr("Their profile"))
            if let profile = state.profile {
                ProfileContent(
                    profile: profile,
                    expandedNoticedID: state.expandedNoticedID,
                    onToggleNoticed: actions.onToggleNoticed
                )
            }
        } buttons: {
            nextButton("Continue")
        }
    }

    // MARK: How Penny decides

    private var howDecides: some View {
        page {
            header(L10n.tr("How Penny decides"), skip: true)
            if let decides = state.decides {
                DecidesContent(decides: decides)
            } else {
                Text("Penny could not work out a forecast yet.").font(.llBody)
            }
        } buttons: {
            nextButton("See their forecast")
        }
    }

    // MARK: Their Next Move

    private var nextMove: some View {
        page {
            header(L10n.tr("Their Next Move"))
            if let card = state.forecastCard {
                // The Money home forecast card (B3.1). "See the maths" goes back to "How Penny decides".
                ForecastCardView(state: card, onSeeMaths: actions.onSeeMaths, onAskPenny: actions.onAskPenny)
            } else {
                Text("Penny could not work out a forecast yet.").font(.llBody)
            }
            Text("You see this card at the top of Money every day.")
                .font(.llLabel)
                .foregroundStyle(Theme.Palette.muted)
                .fixedSize(horizontal: false, vertical: true)
        } buttons: {
            Button("Start", action: actions.onFinish)
                .buttonStyle(.main)
                .accessibilityIdentifier("onboarding.finish")
        }
    }
}

// MARK: - Parts

/// Centres the content in the scroll view's height, less the pinned button. Off: no change.
private struct FillScreenHeight: ViewModifier {
    let isOn: Bool

    func body(content: Content) -> some View {
        if isOn {
            content.containerRelativeFrame(.vertical, alignment: .center) { length, _ in max(0, length - 120) }
        } else {
            content
        }
    }
}

/// "Your money" and "UK data" rows flowing into one clear decision (C2). UK data lists only the student-facing
/// sources (B4).
private struct ProblemArt: View {
    private struct Item: Identifiable {
        var id: String { title }
        var icon: LLIcon?
        var title: String
    }

    private var money: [Item] { [
        .init(icon: .study, title: L10n.tr("Loan")),
        .init(icon: .ribbon, title: L10n.tr("Bursary")),
        .init(icon: .job, title: L10n.tr("Job")),
        .init(icon: .family, title: L10n.tr("Parents")),
        .init(icon: .bank, title: L10n.tr("Bank")),
        .init(icon: .bills, title: L10n.tr("Bills")),
    ] }

    private var data: [Item] { [
        .init(title: L10n.tr("Official facts (gov.uk, SAAS, Student Finance)")),
        .init(title: "Bank of England"),
        .init(title: "ONS"),
        .init(title: "Nomis"),
        .init(title: "Octopus Energy"),
        .init(title: "Frankfurter"),
        .init(title: L10n.tr("Bank of England MPC dates")),
    ] }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            group(L10n.tr("Your money"), items: money, id: "money")
            group(L10n.tr("UK data"), items: data, id: "data")
            HStack(spacing: Theme.Spacing.m) {
                PennyView(mood: .happy, size: 48).accessibilityHidden(true)
                Text("One clear decision").font(.llBodyBold)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, Theme.Spacing.l)
            .padding(.vertical, Theme.Spacing.s)
            .inkSurface(.cardAlt, fill: Theme.Palette.money)
            .foregroundStyle(Theme.Palette.onArea)
            .accessibilityElement(children: .combine)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func group(_ title: String, items: [Item], id: String) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            Text(title).llEyebrow()
            FlowRow(spacing: Theme.Spacing.s) {
                ForEach(items) { item in
                    HStack(spacing: 6) {
                        if let icon = item.icon { LLIconImage(icon, size: 22) }
                        Text(item.title).font(.llLabelBold).fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.horizontal, Theme.Spacing.s)
                    .padding(.vertical, 6)
                    .inkSurface(.chip, lineWidth: Theme.chipOutline)
                }
            }
        }
        .padding(Theme.Spacing.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.card)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text([title, items.map(\.title).joined(separator: ", ")].joined(separator: ": ")))
        .accessibilityIdentifier("onboarding.problem.\(id)")
    }
}

/// One sample student, large (C6): avatar, name, age, uni and city, funding, money in with dates, housing,
/// habit line.
private struct StudentCard: View {
    let sample: OnboardingViewState.SampleCard
    let onPick: () -> Void

    var body: some View {
        Button(action: onPick) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                HStack(alignment: .center, spacing: Theme.Spacing.m) {
                    LLIconImage(sample.avatar.flatMap(LLIcon.init(rawValue:)) ?? .study, size: 72)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(sample.title).font(.llTitle).fixedSize(horizontal: false, vertical: true)
                        let kind = [sample.ageText.map { L10n.tr("Age \($0)") }, sample.kindText].compactMap { $0 }.joined(separator: " · ")
                        if !kind.isEmpty {
                            Text(kind).font(.llBodyBold).foregroundStyle(Theme.Palette.muted)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                    Spacer(minLength: 0)
                    Chevron()
                }
                if let place = sample.placeText {
                    Label(place, icon: .study).font(.llBody).fixedSize(horizontal: false, vertical: true)
                }
                Chip(text: sample.fundingText, fill: Theme.Palette.money)
                if sample.moneyIn.isEmpty {
                    Text(sample.text).font(.llBody).fixedSize(horizontal: false, vertical: true)
                } else {
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        Text("Money in").llEyebrow()
                        ForEach(sample.moneyIn) { line in
                            MoneyInRow(line: line)
                        }
                    }
                    .padding(Theme.Spacing.m)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .inkSurface(.cardAlt, lineWidth: Theme.chipOutline)
                }
                if let housing = sample.housing {
                    Label(housing, icon: .home).font(.llBody).fixedSize(horizontal: false, vertical: true)
                }
                if let habit = sample.habitLine {
                    Label(habit, icon: .goal).font(.llBody).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(Theme.Spacing.xl)
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .inkSurface(.card)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityHint(Text("Builds this student's profile"))
        .accessibilityIdentifier("onboarding.sample.\(sample.id)")
    }
}

/// The one honesty line (B4), under the student list.
private struct HonestyLine: View {
    var body: some View {
        HStack(alignment: .top, spacing: Theme.Spacing.m) {
            LLIconImage(.why, size: 28)
            Text(L10n.tr("These are sample students. UK banks do not give apps like ours access to real accounts without a licence, so Penny runs on sample statements built from real UK figures."))
                .font(.llLabel)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(Theme.Spacing.l)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.cardAlt)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("onboarding.honesty")
    }
}

/// "SAAS loan  £735 a month", then the dates.
private struct MoneyInRow: View {
    let line: OnboardingViewState.MoneyInLine

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(alignment: .firstTextBaseline) {
                Text(line.label).font(.llBody).fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: Theme.Spacing.s)
                Text(line.amountText).font(.llBodyBold).multilineTextAlignment(.trailing)
            }
            if let dates = line.dates {
                Text(dates).font(.llLabel).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
            }
        }
        .accessibilityElement(children: .combine)
    }
}

/// One build stage: status, label, then what the call found (a skeleton line while it runs).
private struct BuildStageRow: View {
    let stage: OnboardingViewState.BuildStage

    var body: some View {
        HStack(alignment: .center, spacing: Theme.Spacing.m) {
            Group {
                switch stage.status {
                case .done: LLIconImage(.check, size: 28)
                case .running: ProgressView().tint(Theme.Palette.ink)
                case .waiting: LLSkeleton(.circle(diameter: 22))
                case .skipped: LLIconImage(.why, size: 24).opacity(0.6)
                }
            }
            .frame(width: 28, height: 28)
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                Text(stage.label)
                    .font(stage.status == .done ? .llBodyBold : .llBody)
                    .foregroundStyle(stage.status == .waiting ? Theme.Palette.muted : Theme.Palette.ink)
                    .fixedSize(horizontal: false, vertical: true)
                if let detail = stage.detail {
                    Text(detail).font(.llLabel).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
                } else if stage.status == .running || stage.status == .waiting {
                    LLSkeleton(.line(width: 0.5, height: 10))
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, Theme.Spacing.l)
        .padding(.vertical, Theme.Spacing.s)
        .frame(minHeight: Theme.minTarget + 8)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text([stage.label, stage.detail].compactMap { $0 }.joined(separator: ". ")))
        .accessibilityValue(Text(statusText))
        .accessibilityIdentifier("onboarding.stage.\(stage.id)")
    }

    private var statusText: LocalizedStringKey {
        switch stage.status {
        case .done: "Done"
        case .running: "In progress"
        case .waiting: "Waiting"
        case .skipped: "Skipped"
        }
    }
}

/// "Their profile": every section hides when its call gave nothing.
private struct ProfileContent: View {
    let profile: OnboardingViewState.Profile
    let expandedNoticedID: String?
    let onToggleNoticed: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
            if profile.name != nil || profile.avatar != nil {
                HStack(spacing: Theme.Spacing.m) {
                    LLIconImage(profile.avatar.flatMap(LLIcon.init(rawValue:)) ?? .study, size: 64)
                    VStack(alignment: .leading, spacing: 2) {
                        if let name = profile.name { Text(name).font(.llTitle) }
                        if let subtitle = profile.subtitle, !subtitle.isEmpty {
                            Text(subtitle).font(.llLabel).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("onboarding.profile.name")
            }
            if !profile.incomes.isEmpty || profile.housing != nil {
                block("Money in") {
                    ForEach(profile.incomes) { MoneyInRow(line: $0) }
                    if let housing = profile.housing {
                        if !profile.incomes.isEmpty { RuleDivider() }
                        Label(housing, icon: .home).font(.llBody).fixedSize(horizontal: false, vertical: true)
                            .accessibilityIdentifier("onboarding.profile.housing")
                    }
                }
            }
            if let period = profile.periodText {
                // Every money block below uses this one period (C7).
                Label(L10n.tr("Spending and bills: \(period)"), icon: .budget)
                    .font(.llBodyBold)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("onboarding.profile.period")
            }
            if !profile.spending.isEmpty {
                block(L10n.tr("Spending by category")) {
                    if let total = profile.spendingTotalText { Text(total).font(.llBodyBold) }
                    SpendingPie(slices: profile.spending, label: [L10n.tr("Spending by category"), profile.periodText].compactMap { $0 }.joined(separator: ", "))
                }
            }
            if !profile.bills.isEmpty {
                block(L10n.tr("Bills and subscriptions")) {
                    if let total = profile.billsTotalText { Text(total).font(.llBodyBold) }
                    ForEach(profile.bills) { row($0) }
                }
                .accessibilityIdentifier("onboarding.profile.bills")
            }
            if !profile.debts.isEmpty || profile.noDebts {
                block("Debts") {
                    if profile.debts.isEmpty {
                        Text("No debts found.").font(.llBody)
                    }
                    ForEach(profile.debts) { row($0) }
                }
            }
            if let savings = profile.savingsText {
                block("Savings") {
                    Text(savings).font(.llTitle)
                    if let cover = profile.coverText { Text(cover).font(.llLabel).foregroundStyle(Theme.Palette.muted) }
                }
                .accessibilityIdentifier("onboarding.profile.savings")
            }
            if !profile.habitParts.isEmpty {
                block("Habit score") {
                    if let overall = profile.habitOverall {
                        Text("\(overall) out of 100").font(.llTitle)
                    }
                    ForEach(profile.habitParts) { part in
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            HStack {
                                Text(part.label).font(.llLabelBold)
                                Spacer()
                                Text("\(part.value)").font(.llLabelBold.monospacedDigit())
                            }
                            InkProgressBar(value: Double(part.value) / 100, color: Theme.Palette.money, height: 14)
                        }
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(Text(part.label))
                        .accessibilityValue(Text("\(part.value) out of 100"))
                        .accessibilityIdentifier("onboarding.habit.\(part.id)")
                    }
                }
            }
            if !profile.noticed.isEmpty {
                VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                    Text(profile.noticed.count == 3 ? "3 things Penny noticed" : "What Penny noticed")
                        .font(.llSection)
                        .accessibilityAddTraits(.isHeader)
                    ForEach(Array(profile.noticed.enumerated()), id: \.element.id) { offset, item in
                        NoticedRow(item: item, color: noticedColors[offset % noticedColors.count],
                                   isOpen: expandedNoticedID == item.id, onTap: { onToggleNoticed(item.id) })
                    }
                }
            }
        }
    }

    private var noticedColors: [Color] { [Theme.Palette.work, Theme.Palette.home, Theme.Palette.family] }

    private func block(_ title: String, @ViewBuilder content: () -> some View) -> some View {
        block(LocalizedStringKey(title), content: content)
    }

    private func block(_ title: LocalizedStringKey, @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Text(title).font(.llSection).accessibilityAddTraits(.isHeader)
            VStack(alignment: .leading, spacing: Theme.Spacing.m) { content() }
                .padding(Theme.Spacing.l)
                .frame(maxWidth: .infinity, alignment: .leading)
                .inkSurface(.card)
        }
    }

    private func row(_ row: OnboardingViewState.ProfileRow) -> some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 2) {
                Text(row.label).font(.llBody).fixedSize(horizontal: false, vertical: true)
                if let detail = row.detail {
                    Text(detail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
            }
            Spacer(minLength: Theme.Spacing.s)
            Text(row.valueText).font(.llBodyBold)
        }
        .accessibilityElement(children: .combine)
    }
}

/// Spending by category as a pie (C7): ink-outlined slices in the forecast colours, then a legend with £ and share.
private struct SpendingPie: View {
    let slices: [OnboardingViewState.SpendSlice]
    let label: String

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Chart(slices) { slice in
                SectorMark(angle: .value("Amount", slice.amount), angularInset: 1)
                    .foregroundStyle(ForecastPalette.slice(slice.colorIndex))
            }
            .chartLegend(.hidden)
            .frame(width: 168, height: 168)
            .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: 2.5))
            .frame(maxWidth: .infinity)
            .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                ForEach(slices) { slice in
                    HStack(spacing: Theme.Spacing.s) {
                        CategoryDot(color: ForecastPalette.slice(slice.colorIndex))
                        Text(slice.label).font(.llBody).fixedSize(horizontal: false, vertical: true)
                        Spacer(minLength: Theme.Spacing.s)
                        Text(slice.amountText).font(.llBodyBold)
                        Text(slice.shareText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                            .frame(minWidth: 40, alignment: .trailing)
                    }
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(Text(label))
        .accessibilityValue(Text(slices.map { "\($0.label) \($0.amountText), \($0.shareText)" }.joined(separator: ". ")))
        .accessibilityIdentifier("onboarding.profile.spendingChart")
    }
}

/// One thing Penny noticed: a small coloured visual and the sentence. Tap shows the evidence.
private struct NoticedRow: View {
    let item: OnboardingViewState.Noticed
    let color: Color
    let isOpen: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                HStack(alignment: .center, spacing: Theme.Spacing.m) {
                    LLIconImage(LLIcon(rawValue: item.icon) ?? .why, size: 32)
                        .padding(6)
                        .inkSurface(.badge, fill: color, lineWidth: Theme.chipOutline)
                    Text(item.text).font(.llBody).fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
                if isOpen {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        Text("Evidence").llEyebrow()
                        ForEach(item.evidence) { row in
                            HStack {
                                Text(row.label).font(.llLabel)
                                Spacer()
                                Text(row.valueText).font(.llLabelBold)
                            }
                        }
                        Text(item.sourceText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                    .transition(.opacity)
                } else {
                    Text("Show the evidence").font(.llLabelBold).foregroundStyle(Theme.Palette.muted)
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(Theme.Spacing.l)
            .frame(maxWidth: .infinity, minHeight: Theme.minTarget, alignment: .leading)
            .inkSurface(.card)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityHint(Text(isOpen ? "Hides the evidence" : "Shows the evidence"))
        .accessibilityIdentifier("onboarding.noticed.\(item.id)")
    }
}

/// "How Penny decides" (C8): the question, the 4 forecast steps with real numbers and sources, the sum, then
/// the result and the comparison with habits.
private struct DecidesContent: View {
    let decides: OnboardingViewState.Decides

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            HStack(alignment: .center, spacing: Theme.Spacing.m) {
                PennyView(mood: .thinking, size: 56).accessibilityHidden(true)
                Text(decides.question)
                    .font(.llTitle)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("onboarding.decides.title")
            }
            VStack(alignment: .leading, spacing: 0) {
                ForEach(Array(decides.steps.enumerated()), id: \.element.id) { offset, step in
                    if offset > 0 { RuleDivider() }
                    StepRow(step: step)
                }
            }
            .inkSurface(.card)
            if let sum = decides.sumLine, let result = decides.resultText {
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    Text(sum).font(.llBody)
                    Text(result).font(.llHero).lineLimit(1).minimumScaleFactor(0.6)
                    if let daily = decides.dailyText { Text(daily).font(.llLabelBold).foregroundStyle(Theme.Palette.muted) }
                }
                .padding(Theme.Spacing.l)
                .frame(maxWidth: .infinity, alignment: .leading)
                .inkSurface(.cardAlt, fill: ForecastPalette.greenTint)
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("onboarding.decides.result")
            }
            if let habit = decides.habitText {
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    Text(decides.verdict).llEyebrow()
                    Text(habit).font(.llBody).fixedSize(horizontal: false, vertical: true)
                    if let source = decides.habitSource {
                        Text(source).font(.llLabel).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
                    }
                }
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("onboarding.decides.habits")
            }
        }
    }

    private struct StepRow: View {
        let step: OnboardingViewState.DecideStep

        var body: some View {
            HStack(alignment: .top, spacing: Theme.Spacing.m) {
                Text("\(step.number)")
                    .font(.llLabelBold)
                    .frame(width: 26, height: 26)
                    .inkSurface(.badge, lineWidth: Theme.chipOutline)
                VStack(alignment: .leading, spacing: 2) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(step.title).font(.llBodyBold).fixedSize(horizontal: false, vertical: true)
                        Spacer(minLength: Theme.Spacing.s)
                        Text(step.amountText).font(.llBodyBold.monospacedDigit()).multilineTextAlignment(.trailing)
                    }
                    if let detail = step.detail {
                        Text(detail).font(.llLabel).fixedSize(horizontal: false, vertical: true)
                    }
                    if !step.sources.isEmpty {
                        Text(L10n.tr("Source: \(step.sources.joined(separator: ", "))"))
                            .font(.llLabel).foregroundStyle(Theme.Palette.muted)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
            .padding(.horizontal, Theme.Spacing.l)
            .padding(.vertical, Theme.Spacing.m)
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("onboarding.decides.step.\(step.number)")
        }
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
#Preview("Problem · light") { OnboardingView(state: OnboardingFixtures.problem) }
#Preview("Problem · dark") { OnboardingView(state: OnboardingFixtures.problem).previewDark() }
#Preview("Problem · AX3") { OnboardingView(state: OnboardingFixtures.problem).previewLargeType() }
#Preview("Language, French · light") { OnboardingView(state: OnboardingFixtures.languageFrench) }
#Preview("Language · dark") { OnboardingView(state: OnboardingFixtures.language).previewDark() }
#Preview("Language · AX3") { OnboardingView(state: OnboardingFixtures.language).previewLargeType() }
#Preview("What you can do · light") { OnboardingView(state: OnboardingFixtures.features) }
#Preview("What you can do · dark") { OnboardingView(state: OnboardingFixtures.features).previewDark() }
#Preview("What you can do · AX3") { OnboardingView(state: OnboardingFixtures.features).previewLargeType() }
#Preview("Pick your student · light") { OnboardingView(state: OnboardingFixtures.pickStudent) }
#Preview("Pick your student · dark") { OnboardingView(state: OnboardingFixtures.pickStudent).previewDark() }
#Preview("Pick your student · AX3") { OnboardingView(state: OnboardingFixtures.pickStudent).previewLargeType() }
#Preview("Pick your student, older server · light") { OnboardingView(state: OnboardingFixtures.pickStudentOldServer) }
#Preview("Pick your student, loading · light") { OnboardingView(state: OnboardingFixtures.samplesLoading) }
#Preview("Pick your student, error · dark") { OnboardingView(state: OnboardingFixtures.connectError).previewDark() }
#Preview("Sign in · light") { OnboardingView(state: OnboardingFixtures.signInDemoOnly) }
#Preview("Building · light") { OnboardingView(state: OnboardingFixtures.building) }
#Preview("Building · dark") { OnboardingView(state: OnboardingFixtures.building).previewDark() }
#Preview("Building, done · AX3") { OnboardingView(state: OnboardingFixtures.buildingDone).previewLargeType() }
#Preview("Their profile · light") { OnboardingView(state: OnboardingFixtures.profile) }
#Preview("Their profile, evidence · dark") { OnboardingView(state: OnboardingFixtures.profileEvidence).previewDark() }
#Preview("Their profile · AX3") { OnboardingView(state: OnboardingFixtures.profile).previewLargeType() }
#Preview("How Penny decides · light") { OnboardingView(state: OnboardingFixtures.howDecides) }
#Preview("How Penny decides · dark") { OnboardingView(state: OnboardingFixtures.howDecides).previewDark() }
#Preview("How Penny decides · AX3") { OnboardingView(state: OnboardingFixtures.howDecides).previewLargeType() }
#Preview("How Penny decides, running short · light") { OnboardingView(state: OnboardingFixtures.howDecidesShort) }
#Preview("Their Next Move · light") { OnboardingView(state: OnboardingFixtures.nextMove) }
#Preview("Their Next Move · dark") { OnboardingView(state: OnboardingFixtures.nextMove).previewDark() }
#Preview("Their Next Move · AX3") { OnboardingView(state: OnboardingFixtures.nextMove).previewLargeType() }
#Preview("Their Next Move, running short · light") { OnboardingView(state: OnboardingFixtures.nextMoveShort) }
