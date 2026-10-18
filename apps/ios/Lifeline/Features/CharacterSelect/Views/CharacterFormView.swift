import SwiftUI

/// Manual character entry for "Play yourself" and God Mode.
struct CharacterFormView: View {
    let state: CharacterFormViewState
    var actions: CharacterFormActions = .noop
    @Environment(\.dismiss) private var dismiss

    private func field<T>(_ keyPath: WritableKeyPath<CharacterFormFields, T>) -> Binding<T> {
        Binding(
            get: { state.fields[keyPath: keyPath] },
            set: { value in
                var fields = state.fields
                fields[keyPath: keyPath] = value
                actions.onChange(fields)
            }
        )
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: state.title, leading: HeaderSquareButton(kind: .back, identifier: "form.back") { dismiss() }) { EmptyView() }
                if !state.quickPicks.isEmpty {
                    RowGroupTitle(text: L10n.tr("Quick pick"))
                    FlowRow(spacing: Theme.Spacing.s) {
                        ForEach(state.quickPicks) { pick in
                            Button { actions.onQuickPick(pick.id) } label: {
                                Label(pick.label, icon: LLIcon.face(emoji: pick.emoji)).font(.llLabelBold).padding(.horizontal, Theme.Spacing.m)
                                    .frame(minHeight: Theme.minTarget)
                                    .inkSurface(.chip, lineWidth: Theme.chipOutline)
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("form.quickPick.\(pick.id)")
                        }
                    }
                }
                if state.showsBankConnect {
                    Button(action: actions.onConnectBank) {
                        ListRow(icon: .bank, title: L10n.tr("Fill in from my bank"), subtitle: state.bankStatusText)
                            .padding(.horizontal, Theme.Spacing.l)
                            .inkSurface(.card)
                    }
                    .buttonStyle(.plain)
                    .accessibilityIdentifier("form.connectBank")
                }
                RowGroupTitle(text: "You")
                LLTextField(title: "Name", text: field(\.name), identifier: "form.name")
                    .textContentType(.givenName)
                LLStepper(
                    title: L10n.tr("Born in"),
                    valueText: String(state.fields.birthYear),
                    canDecrement: state.fields.birthYear > state.birthYearRange.lowerBound,
                    canIncrement: state.fields.birthYear < state.birthYearRange.upperBound,
                    identifier: "form.birthYear",
                    onDecrement: { change(\.birthYear, state.fields.birthYear - 1) },
                    onIncrement: { change(\.birthYear, state.fields.birthYear + 1) }
                )
                LLTextField(title: L10n.tr("Job, for example nurse"), text: field(\.occupation), identifier: "form.occupation")
                    .textContentType(.jobTitle)
                RowGroupTitle(text: L10n.tr("Where you live"))
                LLChoiceChips(
                    title: "Region",
                    options: state.regions.map { .init(id: $0.id, label: $0.label) },
                    selection: state.fields.regionID,
                    identifier: "form.region"
                ) { change(\.regionID, $0) }
                LLTextField(title: "Town", text: field(\.town), identifier: "form.town")
                    .textContentType(.addressCity)
                LLChoiceChips(
                    title: "Home",
                    options: HousingOption.allCases.map { .init(id: $0.rawValue, label: $0.label) },
                    selection: state.fields.housing.rawValue,
                    identifier: "form.housing"
                ) { if let option = HousingOption(rawValue: $0) { change(\.housing, option) } }
                RowGroupTitle(text: "Money")
                LLMoneyField(title: L10n.tr("Pay before tax, per year"), value: field(\.income), identifier: "form.income")
                LLMoneyField(title: "Savings", value: field(\.savings), identifier: "form.savings")
                LLMoneyField(title: L10n.tr("Debts (card, overdraft, Klarna)"), value: field(\.debt), identifier: "form.debt")
                Text(state.footer).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s).padding(.bottom, Theme.Spacing.m)
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            Button("Choose a start year", action: actions.onContinue)
                .buttonStyle(.main)
                .disabled(!state.canContinue)
                .accessibilityIdentifier("form.continue")
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.vertical, Theme.Spacing.m)
                .background(Theme.Palette.paper.ignoresSafeArea(edges: .bottom))
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    private func change<T>(_ keyPath: WritableKeyPath<CharacterFormFields, T>, _ value: T) {
        var fields = state.fields
        fields[keyPath: keyPath] = value
        actions.onChange(fields)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Play yourself · light") {
    CharacterFormView(state: Fixtures.CharacterForm.playYourself).previewInNavigation()
}

#Preview("Play yourself · dark") {
    CharacterFormView(state: Fixtures.CharacterForm.playYourself).previewInNavigation().previewDark()
}

#Preview("Play yourself · AX3") {
    CharacterFormView(state: Fixtures.CharacterForm.playYourself).previewInNavigation().previewLargeType()
}

#Preview("Bank filled · light") {
    CharacterFormView(state: Fixtures.CharacterForm.bankFilled).previewInNavigation()
}

#Preview("Bank filled · dark") {
    CharacterFormView(state: Fixtures.CharacterForm.bankFilled).previewInNavigation().previewDark()
}

#Preview("Bank filled · AX3") {
    CharacterFormView(state: Fixtures.CharacterForm.bankFilled).previewInNavigation().previewLargeType()
}

