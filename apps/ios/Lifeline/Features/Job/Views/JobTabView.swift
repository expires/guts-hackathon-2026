import SwiftUI

/// Job tab: current job and job actions.
struct JobTabView: View {
    let state: JobTabViewState
    var actions: ActionTabActions = .noop

    var body: some View {
        ScrollView {
            VStack(spacing: Theme.Spacing.l) {
                GlassCard {
                    if let job = state.job {
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            Text(job.title).font(.title2.bold())
                            if let employer = job.employer {
                                Text(employer).foregroundStyle(.secondary)
                            }
                            Text("\(Money.format(job.annualIncome)) a year")
                                .font(.headline.monospacedDigit())
                                .contentTransition(.numericText(value: job.annualIncome))
                            Text(job.yearsInRole == 1 ? "1 year in this job" : "\(job.yearsInRole) years in this job")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                            if let status = job.employerStatus {
                                Label(status, systemImage: "exclamationmark.triangle.fill")
                                    .foregroundStyle(job.employerAtRisk ? .orange : .secondary)
                            }
                        }
                        .accessibilityElement(children: .combine)
                    } else {
                        Text("You do not have a job.").foregroundStyle(.secondary)
                    }
                }
                if let outcome = state.outcome {
                    OutcomeBanner(outcome: outcome, onDismiss: actions.onDismissOutcome)
                }
                SectionTitle(text: "What to do")
                ActionList(actions: state.actions, isBusy: state.isBusy, onAction: actions.onAction)
            }
            .padding(Theme.Spacing.l)
        }
        .navigationTitle("Job")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Job · light") {
    JobTabView(state: Fixtures.Tabs.job).previewInNavigation()
}

#Preview("Job · dark") {
    JobTabView(state: Fixtures.Tabs.job).previewInNavigation().previewDark()
}

#Preview("Job · AX3") {
    JobTabView(state: Fixtures.Tabs.job).previewInNavigation().previewLargeType()
}

#Preview("At risk · light") {
    JobTabView(state: Fixtures.Tabs.jobAtRisk).previewInNavigation()
}

#Preview("At risk · dark") {
    JobTabView(state: Fixtures.Tabs.jobAtRisk).previewInNavigation().previewDark()
}

#Preview("At risk · AX3") {
    JobTabView(state: Fixtures.Tabs.jobAtRisk).previewInNavigation().previewLargeType()
}

#Preview("No job · light") {
    JobTabView(state: Fixtures.Tabs.noJob).previewInNavigation()
}

#Preview("No job · dark") {
    JobTabView(state: Fixtures.Tabs.noJob).previewInNavigation().previewDark()
}

#Preview("No job · AX3") {
    JobTabView(state: Fixtures.Tabs.noJob).previewInNavigation().previewLargeType()
}
