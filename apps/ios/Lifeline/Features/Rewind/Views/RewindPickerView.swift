import SwiftUI

/// Pick a past decision to go back to.
struct RewindPickerView: View {
    let state: RewindPickerViewState
    var actions: RewindActions = .noop

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Label(state.allowanceText, systemImage: "backward.fill")
                    if state.needsPass {
                        Button(action: actions.onBuyPass) {
                            HStack {
                                Text("Get the Rewind Pass")
                                Spacer()
                                Text(Brand.demoPaymentLabel).font(.caption).foregroundStyle(.secondary)
                            }
                            .frame(minHeight: Theme.minTarget)
                        }
                        .accessibilityIdentifier("rewind.buyPass")
                    }
                }
                Section("Your past choices") {
                    if state.options.isEmpty {
                        Text("No choices yet. Answer an event first.").foregroundStyle(.secondary)
                    }
                    ForEach(state.options) { option in
                        Button { actions.onPick(option.id) } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text("\(String(option.year)) · Age \(option.age)").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                                Text(option.text).foregroundStyle(.primary)
                                Text("Net worth then: \(Money.format(option.netWorth))").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                            }
                            .frame(minHeight: Theme.minTarget, alignment: .leading)
                        }
                        .disabled(state.needsPass || state.isSubmitting)
                        .accessibilityIdentifier("rewind.option.\(option.id)")
                    }
                }
            }
            .navigationTitle("Rewind")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel", action: actions.onClose)
                }
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Picker · light") {
    RewindPickerView(state: Fixtures.Rewind.picker)
}

#Preview("Picker · dark") {
    RewindPickerView(state: Fixtures.Rewind.picker).previewDark()
}

#Preview("Picker · AX3") {
    RewindPickerView(state: Fixtures.Rewind.picker).previewLargeType()
}

#Preview("Needs pass · light") {
    RewindPickerView(state: Fixtures.Rewind.needsPass)
}

#Preview("Needs pass · dark") {
    RewindPickerView(state: Fixtures.Rewind.needsPass).previewDark()
}

#Preview("Needs pass · AX3") {
    RewindPickerView(state: Fixtures.Rewind.needsPass).previewLargeType()
}
