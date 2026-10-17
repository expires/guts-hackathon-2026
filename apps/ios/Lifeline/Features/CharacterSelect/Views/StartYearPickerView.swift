import SwiftUI

/// Pick the year the life starts.
struct StartYearPickerView: View {
    let state: StartYearPickerViewState
    var actions: StartYearPickerActions = .noop

    var body: some View {
        VStack(spacing: Theme.Spacing.xl) {
            if state.usesSampleData {
                DemoDataBadge().frame(maxWidth: .infinity, alignment: .leading)
            }
            GlassCard {
                HStack(spacing: Theme.Spacing.l) {
                    Text(state.emoji)
                        .font(.system(size: 56))
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        Text(state.name).font(.title2.bold())
                        Text("\(state.occupation), \(state.town)")
                            .foregroundStyle(.secondary)
                        Text("Born \(String(state.birthYear))")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                }
                .accessibilityElement(children: .combine)
            }

            VStack(spacing: Theme.Spacing.s) {
                Text("Start year").font(.headline)
                Picker("Start year", selection: Binding(get: { state.selectedYear }, set: actions.onYearChange)) {
                    ForEach(Array(state.years), id: \.self) { value in
                        Text(String(value)).tag(value)
                    }
                }
                .pickerStyle(.wheel)
                .frame(maxHeight: 180)
                .accessibilityIdentifier("startYear.picker")
                Text("\(state.name) is \(state.ageAtStart) in \(String(state.selectedYear)).")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .contentTransition(.numericText(value: Double(state.selectedYear)))
                    .accessibilityIdentifier("startYear.summary")
            }

            Spacer(minLength: 0)

            PrimaryButton(title: "Start life", isBusy: state.isStarting, action: actions.onStart)
                .disabled(state.isStarting)
                .accessibilityLabel("Start life in \(String(state.selectedYear))")
                .accessibilityIdentifier("startYear.start")
        }
        .padding(Theme.Spacing.l)
        .navigationTitle("When to start")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Preset · light") {
    StartYearPickerView(state: Fixtures.StartYear.preset).previewInNavigation()
}

#Preview("Preset · dark") {
    StartYearPickerView(state: Fixtures.StartYear.preset).previewInNavigation().previewDark()
}

#Preview("Preset · AX3") {
    StartYearPickerView(state: Fixtures.StartYear.preset).previewInNavigation().previewLargeType()
}

#Preview("Starting · light") {
    StartYearPickerView(state: Fixtures.StartYear.starting).previewInNavigation()
}

#Preview("Starting · dark") {
    StartYearPickerView(state: Fixtures.StartYear.starting).previewInNavigation().previewDark()
}

#Preview("Starting · AX3") {
    StartYearPickerView(state: Fixtures.StartYear.starting).previewInNavigation().previewLargeType()
}
