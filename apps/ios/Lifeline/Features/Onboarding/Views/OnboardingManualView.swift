import SwiftUI

/// "Enter your numbers": postcode, home, take-home pay, regular costs, savings.
struct OnboardingManualView: View {
    let manual: OnboardingViewState.Manual
    var isBusy = false
    var errorMessage: String?
    var actions: OnboardingActions = .noop

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: "Your numbers", leading: HeaderSquareButton(kind: .back, identifier: "onboarding.back", action: actions.onBack))
                Text("Round numbers are fine. You can change them later.")
                    .font(.llBody)
                    .fixedSize(horizontal: false, vertical: true)
                studentOrWorking
                postcode
                LLChoiceChips(
                    title: "Your home",
                    options: OnboardingViewState.Manual.Housing.allCases.map { .init(id: $0.rawValue, label: $0.label) },
                    selection: manual.housing.rawValue,
                    identifier: "onboarding.manual.housing"
                ) { id in
                    if let housing = OnboardingViewState.Manual.Housing(rawValue: id) { change { $0.housing = housing } }
                }
                housingFields
                if manual.isStudent {
                    incomes
                    LLChoiceChips(
                        title: "Student loan plan",
                        options: OnboardingViewState.LoanPlan.allCases.map { .init(id: $0.rawValue, label: $0.label) },
                        selection: manual.loanPlan?.rawValue ?? "",
                        identifier: "onboarding.manual.loanPlan"
                    ) { id in change { $0.loanPlan = OnboardingViewState.LoanPlan(rawValue: id) } }
                } else {
                    LLMoneyField(title: "Take-home pay a month", value: binding(\.monthlyTakeHome), identifier: "onboarding.manual.takeHome")
                }
                costs
                debts
                LLMoneyField(title: "Savings", value: binding(\.savings), identifier: "onboarding.manual.savings")
                if !manual.problems.isEmpty {
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        ForEach(manual.problems, id: \.self) { Text($0).font(.llBodyBold) }
                    }
                    .foregroundStyle(Theme.Palette.onArea)
                    .padding(Theme.Spacing.l)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .inkSurface(.cardAlt, fill: Theme.Palette.health)
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("onboarding.manual.problems")
                }
                if let errorMessage { OnboardingErrorCard(message: errorMessage, onDismiss: actions.onDismissError) }
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .scrollDismissesKeyboard(.interactively)
        .safeAreaInset(edge: .bottom, spacing: 0) {
            PrimaryButton(title: "Save my numbers", isBusy: isBusy, action: actions.onSaveManual)
                .disabled(isBusy)
                .accessibilityIdentifier("onboarding.manual.save")
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.vertical, Theme.Spacing.m)
                .background(Theme.Palette.paper.ignoresSafeArea(edges: .bottom))
        }
        .paperBackground()
    }

    private var studentOrWorking: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            LLSegmented(
                options: [.init(id: "student", label: "Student"), .init(id: "working", label: "Working")],
                selection: manual.isStudent ? "student" : "working"
            ) { id in change { $0.isStudent = id == "student" } }
            .accessibilityIdentifier("onboarding.manual.studentOrWorking")
            LLStepper(
                title: "Your age",
                valueText: manual.age.map(String.init) ?? "Not set",
                canDecrement: (manual.age ?? 17) > 16,
                canIncrement: (manual.age ?? 0) < 100,
                identifier: "onboarding.manual.age",
                onDecrement: { change { $0.age = max(16, ($0.age ?? 19) - 1) } },
                onIncrement: { change { $0.age = min(100, ($0.age ?? 17) + 1) } }
            )
        }
    }

    /// Each way money arrives: on/off, then the amount per payment and how often it comes.
    private var incomes: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            Text("How money arrives").font(.llLabelBold)
            Text("Turn on each one you get. Maintenance loans usually come 3 times a year (monthly in Scotland).")
                .font(.llLabel)
                .foregroundStyle(Theme.Palette.muted)
                .fixedSize(horizontal: false, vertical: true)
            RowGroup {
                ForEach(manual.incomes) { income in
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        LLToggleRow(title: income.kind.label, isOn: income.isOn, identifier: "onboarding.manual.income.\(income.id)") { _ in
                            actions.onToggleIncome(income.id)
                        }
                        if income.isOn {
                            LLMoneyField(title: "Amount each time", value: incomeBinding(income.id), identifier: "onboarding.manual.income.\(income.id).amount")
                            LLSegmented(
                                options: OnboardingViewState.IncomeRow.Schedule.allCases.map { .init(id: $0.rawValue, label: $0.label) },
                                selection: income.schedule.rawValue
                            ) { id in
                                guard let schedule = OnboardingViewState.IncomeRow.Schedule(rawValue: id) else { return }
                                change { manual in
                                    if let index = manual.incomes.firstIndex(where: { $0.id == income.id }) { manual.incomes[index].schedule = schedule }
                                }
                            }
                            .padding(.bottom, Theme.Spacing.s)
                        }
                    }
                }
            }
        }
    }

    /// Card, overdraft and buy now, pay later balances.
    private var debts: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            Text("What you owe").font(.llLabelBold)
            RowGroup {
                ForEach(manual.debts) { debt in
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        LLToggleRow(title: debt.kind.label, isOn: debt.isOn, identifier: "onboarding.manual.debt.\(debt.id)") { _ in
                            actions.onToggleDebt(debt.id)
                        }
                        if debt.isOn {
                            LLMoneyField(title: "You owe", value: debtBinding(debt.id), identifier: "onboarding.manual.debt.\(debt.id).balance")
                                .padding(.bottom, Theme.Spacing.s)
                        }
                    }
                }
            }
        }
    }

    private var postcode: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            LLTextField(title: "Postcode", text: binding(\.postcode), identifier: "onboarding.manual.postcode")
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
            HStack(spacing: Theme.Spacing.m) {
                Button(action: actions.onUseLocation) {
                    HStack(spacing: Theme.Spacing.s) {
                        if manual.isLocating { ProgressView().tint(Theme.Palette.ink) } else { LLIconImage(.home, size: 24) }
                        Text("Use my location").lineLimit(1).minimumScaleFactor(0.8)
                    }
                }
                .buttonStyle(SecondButtonStyle(shape: .buttonThird))
                .disabled(manual.isLocating)
                .accessibilityIdentifier("onboarding.manual.location")
            }
            if let note = manual.locationNote {
                Text(note).font(.llLabel).foregroundStyle(Theme.Palette.muted).accessibilityIdentifier("onboarding.manual.locationNote")
            }
        }
    }

    @ViewBuilder
    private var housingFields: some View {
        switch manual.housing {
        case .rent:
            LLMoneyField(title: "Rent a month", value: binding(\.monthlyRent), identifier: "onboarding.manual.rent")
        case .mortgage:
            LLMoneyField(title: "Mortgage left to pay", value: binding(\.mortgageBalance), identifier: "onboarding.manual.mortgageBalance")
            PercentField(title: "Mortgage rate (%)", value: binding(\.mortgageRatePercent), identifier: "onboarding.manual.rate")
            LLStepper(
                title: "Your deal ends",
                valueText: manual.dealEndText,
                canDecrement: manual.dealEndYear > manual.dealEndYears.lowerBound || manual.dealEndMonth > 1,
                canIncrement: manual.dealEndYear < manual.dealEndYears.upperBound || manual.dealEndMonth < 12,
                identifier: "onboarding.manual.dealEnd",
                onDecrement: { change { Self.shiftMonth(&$0, by: -1) } },
                onIncrement: { change { Self.shiftMonth(&$0, by: 1) } }
            )
        case .own, .parents:
            EmptyView()
        }
    }

    private var costs: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            Text("Regular costs a month").font(.llLabelBold)
            Text("For example council tax, energy, phone, travel.")
                .font(.llLabel)
                .foregroundStyle(Theme.Palette.muted)
            ForEach(manual.costs) { cost in
                HStack(alignment: .bottom, spacing: Theme.Spacing.s) {
                    LLTextField(title: "Name", text: costBinding(cost.id, \.name), identifier: "onboarding.manual.cost.\(cost.id).name")
                    LLMoneyField(title: "A month", value: costBinding(cost.id, \.monthlyAmount), identifier: "onboarding.manual.cost.\(cost.id).amount")
                        .frame(maxWidth: 130)
                    HeaderSquareButton(kind: .close, identifier: "onboarding.manual.cost.\(cost.id).remove") { actions.onRemoveCost(cost.id) }
                        .padding(.bottom, 4)
                        .accessibilityLabel("Remove \(cost.name.isEmpty ? "cost" : cost.name)")
                }
            }
            if manual.costs.count < 30 {
                Button("Add a cost", action: actions.onAddCost)
                    .buttonStyle(.text)
                    .accessibilityIdentifier("onboarding.manual.addCost")
            }
        }
    }

    // MARK: Bindings that route every edit through the ViewModel

    private func change(_ edit: (inout OnboardingViewState.Manual) -> Void) {
        var copy = manual
        edit(&copy)
        actions.onManualChange(copy)
    }

    private func binding<Value>(_ keyPath: WritableKeyPath<OnboardingViewState.Manual, Value>) -> Binding<Value> {
        Binding(get: { manual[keyPath: keyPath] }, set: { value in change { $0[keyPath: keyPath] = value } })
    }

    private func costBinding<Value>(_ id: Int, _ keyPath: WritableKeyPath<OnboardingViewState.CostRow, Value>) -> Binding<Value> {
        Binding(
            get: { manual.costs.first { $0.id == id }.map { $0[keyPath: keyPath] } ?? OnboardingViewState.CostRow(id: id, name: "", monthlyAmount: 0)[keyPath: keyPath] },
            set: { value in change { manual in
                if let index = manual.costs.firstIndex(where: { $0.id == id }) { manual.costs[index][keyPath: keyPath] = value }
            } }
        )
    }

    private func incomeBinding(_ id: String) -> Binding<Double> {
        Binding(
            get: { manual.incomes.first { $0.id == id }?.amount ?? 0 },
            set: { value in change { manual in
                if let index = manual.incomes.firstIndex(where: { $0.id == id }) { manual.incomes[index].amount = max(0, value) }
            } }
        )
    }

    private func debtBinding(_ id: String) -> Binding<Double> {
        Binding(
            get: { manual.debts.first { $0.id == id }?.balance ?? 0 },
            set: { value in change { manual in
                if let index = manual.debts.firstIndex(where: { $0.id == id }) { manual.debts[index].balance = max(0, value) }
            } }
        )
    }

    static func shiftMonth(_ manual: inout OnboardingViewState.Manual, by delta: Int) {
        var total = manual.dealEndYear * 12 + (manual.dealEndMonth - 1) + delta
        let low = manual.dealEndYears.lowerBound * 12
        let high = manual.dealEndYears.upperBound * 12 + 11
        total = min(max(total, low), high)
        manual.dealEndYear = total / 12
        manual.dealEndMonth = total % 12 + 1
    }
}

/// Outlined decimal field (17 pt, 52 pt tall), for a percentage.
private struct PercentField: View {
    let title: String
    @Binding var value: Double
    var identifier = ""

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(title).font(.llLabelBold)
            TextField(title, value: $value, format: .number.precision(.fractionLength(0...2)))
                .font(.llBody)
                .keyboardType(.decimalPad)
                .padding(.horizontal, Theme.Spacing.m)
                .frame(minHeight: Theme.buttonHeight)
                .inkSurface(.buttonAlt)
                .accessibilityIdentifier(identifier)
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Manual, mortgage · light") { OnboardingManualView(manual: OnboardingFixtures.manualMortgage) }
#Preview("Manual, mortgage · dark") { OnboardingManualView(manual: OnboardingFixtures.manualMortgage).previewDark() }
#Preview("Manual, mortgage · AX3") { OnboardingManualView(manual: OnboardingFixtures.manualMortgage).previewLargeType() }
#Preview("Manual, student · light") { OnboardingManualView(manual: OnboardingFixtures.manualStudent) }
#Preview("Manual, student · dark") { OnboardingManualView(manual: OnboardingFixtures.manualStudent).previewDark() }
#Preview("Manual, student · AX3") { OnboardingManualView(manual: OnboardingFixtures.manualStudent).previewLargeType() }
#Preview("Manual, problems · light") { OnboardingManualView(manual: OnboardingFixtures.manualProblems) }
