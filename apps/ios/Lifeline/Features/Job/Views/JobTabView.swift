import SwiftUI

/// Job tab: current job and job actions.
struct JobTabView: View {
    let state: JobTabViewState
    var actions: ActionTabActions = .noop

    var body: some View {
        SheetContainer(title: "Job", closeIdentifier: "menu.close", onClose: actions.onClose) {
            if let job = state.job {
                RowGroup(title: L10n.tr("My job")) {
                    ListRow(icon: .job, title: job.title, subtitle: [job.employer, job.yearsInRole == 1 ? "1 year in this job" : L10n.tr("\(job.yearsInRole) years in this job")].compactMap { $0 }.joined(separator: " · "), trailing: Money.format(job.annualIncome), showsChevron: false)
                    if let status = job.employerStatus {
                        ListRow(icon: .jobLoss, title: status, showsChevron: false)
                    }
                }
            } else {
                RowGroup(title: L10n.tr("My job")) {
                    ListRow(icon: .job, title: L10n.tr("No job right now"), showsChevron: false)
                }
            }
            RowGroupTitle(text: L10n.tr("What you can do"))
            ActionList(actions: state.actions, isBusy: state.isBusy, onAction: actions.onAction, emptyText: L10n.tr("Nothing to do here this year."))
        }
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
