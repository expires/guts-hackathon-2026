import SwiftUI

/// Manual character entry for "Play yourself" and God Mode.
struct CharacterFormView: View {
    let state: CharacterFormViewState
    var actions: CharacterFormActions = .noop

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
        Form {
            if !state.quickPicks.isEmpty {
                Section("Quick pick") {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack {
                            ForEach(state.quickPicks) { pick in
                                Button("\(pick.emoji) \(pick.label)") { actions.onQuickPick(pick.id) }
                                    .buttonStyle(.glass)
                                    .frame(minHeight: Theme.minTarget)
                                    .accessibilityIdentifier("form.quickPick.\(pick.id)")
                            }
                        }
                    }
                }
            }
            if state.showsBankConnect {
                Section {
                    Button("Fill in from my bank", systemImage: "building.columns", action: actions.onConnectBank)
                        .frame(minHeight: Theme.minTarget)
                        .accessibilityIdentifier("form.connectBank")
                    if let status = state.bankStatusText {
                        Label(status, systemImage: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                    }
                }
            }
            Section("You") {
                TextField("Name", text: field(\.name))
                    .textContentType(.givenName)
                    .accessibilityIdentifier("form.name")
                Stepper("Born in \(String(state.fields.birthYear))", value: field(\.birthYear), in: state.birthYearRange)
                    .accessibilityIdentifier("form.birthYear")
                TextField("Job, for example nurse", text: field(\.occupation))
                    .textContentType(.jobTitle)
                    .accessibilityIdentifier("form.occupation")
            }
            Section("Where you live") {
                Picker("Region", selection: field(\.regionID)) {
                    ForEach(state.regions) { Text($0.label).tag($0.id) }
                }
                TextField("Town", text: field(\.town))
                    .textContentType(.addressCity)
                    .accessibilityIdentifier("form.town")
                Picker("Home", selection: field(\.housing)) {
                    ForEach(HousingOption.allCases) { Text($0.label).tag($0) }
                }
            }
            Section("Money") {
                MoneyField(title: "Pay before tax, per year", value: field(\.income), identifier: "form.income")
                MoneyField(title: "Savings", value: field(\.savings), identifier: "form.savings")
                MoneyField(title: "Debts, not counting a mortgage", value: field(\.debt), identifier: "form.debt")
            }
            Section {
                Button(action: actions.onContinue) {
                    Text("Choose a start year")
                        .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                }
                .buttonStyle(.glassProminent)
                .disabled(!state.canContinue)
                .accessibilityIdentifier("form.continue")
            } footer: {
                Text(state.footer)
            }
        }
        .navigationTitle(state.title)
    }
}

/// Pounds entry field with a GBP format.
struct MoneyField: View {
    let title: String
    @Binding var value: Double
    let identifier: String

    var body: some View {
        LabeledContent(title) {
            TextField(title, value: $value, format: .currency(code: "GBP").locale(Money.locale).precision(.fractionLength(0)))
                .keyboardType(.numberPad)
                .multilineTextAlignment(.trailing)
                .accessibilityIdentifier(identifier)
        }
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

#Preview("God Mode · light") {
    CharacterFormView(state: Fixtures.CharacterForm.godMode).previewInNavigation()
}

#Preview("God Mode · dark") {
    CharacterFormView(state: Fixtures.CharacterForm.godMode).previewInNavigation().previewDark()
}

#Preview("God Mode · AX3") {
    CharacterFormView(state: Fixtures.CharacterForm.godMode).previewInNavigation().previewLargeType()
}
