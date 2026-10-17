import SwiftUI

/// Pick the year the life starts.
struct StartYearPickerView: View {
    let state: StartYearPickerViewState
    var actions: StartYearPickerActions = .noop
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: "When to start", leading: HeaderSquareButton(kind: .back, identifier: "startYear.back") { dismiss() }) {
                    if state.usesSampleData { DemoDataBadge() }
                }
                HStack(spacing: Theme.Spacing.l) {
                    LLIconImage(LLIcon.face(emoji: state.emoji), size: 64)
                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                        Text(state.name).font(.llTitle)
                        Text("\(state.occupation), \(state.town)").font(.llBody).foregroundStyle(Theme.Palette.muted)
                        Text("Born \(String(state.birthYear))").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                }
                .padding(Theme.Spacing.l)
                .frame(maxWidth: .infinity, alignment: .leading)
                .inkSurface(.card)
                .accessibilityElement(children: .combine)
                LLStepper(
                    title: "Start year",
                    valueText: String(state.selectedYear),
                    canDecrement: state.selectedYear > state.years.lowerBound,
                    canIncrement: state.selectedYear < state.years.upperBound,
                    identifier: "startYear.picker",
                    onDecrement: { actions.onYearChange(state.selectedYear - 1) },
                    onIncrement: { actions.onYearChange(state.selectedYear + 1) }
                )
                LLSegmented(
                    options: quickYears.map { .init(id: String($0), label: String($0)) },
                    selection: String(state.selectedYear)
                ) { if let year = Int($0) { actions.onYearChange(year) } }
                Text("\(state.name) is \(state.ageAtStart) in \(String(state.selectedYear)).")
                    .font(.llBody)
                    .contentTransition(.numericText(value: Double(state.selectedYear)))
                    .accessibilityIdentifier("startYear.summary")
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.vertical, Theme.Spacing.xl)
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            PrimaryButton(title: "Start life", isBusy: state.isStarting, action: actions.onStart)
                .disabled(state.isStarting)
                .accessibilityLabel("Start life in \(String(state.selectedYear))")
                .accessibilityIdentifier("startYear.start")
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.vertical, Theme.Spacing.m)
                .background(Theme.Palette.paper.ignoresSafeArea(edges: .bottom))
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    /// Shortcut years inside the allowed range: the first year, 2008, 2021 and the last year.
    private var quickYears: [Int] {
        var years = [state.years.lowerBound, 2008, 2021, state.years.upperBound].filter { state.years.contains($0) }
        years = years.reduce(into: [Int]()) { if !$0.contains($1) { $0.append($1) } }
        return years.sorted()
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
