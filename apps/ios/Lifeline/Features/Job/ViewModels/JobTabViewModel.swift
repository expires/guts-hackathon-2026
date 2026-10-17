import Foundation
import Observation

@MainActor
@Observable
final class JobTabViewModel {
    private let session: GameSession

    init(session: GameSession) {
        self.session = session
    }

    var state: JobTabViewState {
        Self.makeState(life: session.life, isBusy: session.isBusy, outcome: ActionTabSupport.outcome(session))
    }

    var actions: ActionTabActions {
        ActionTabActions(
            onAction: { [weak self] in
                guard let self else { return }
                ActionTabSupport.perform(session, tab: .job, actionID: $0)
            },
            onDismissOutcome: { [weak self] in self?.session.dismissOutcome() }
        )
    }

    static func makeState(life: Life?, isBusy: Bool, outcome: OutcomeState?) -> JobTabViewState {
        let job = life?.job.map { job in
            JobTabViewState.JobInfo(
                title: job.title,
                employer: job.employer,
                annualIncome: job.annualIncome,
                yearsInRole: job.yearsInRole ?? 0,
                employerStatus: job.employerStatus == .insolvent ? "Employer in trouble" : nil,
                employerAtRisk: job.employerStatus == .insolvent
            )
        }
        return JobTabViewState(
            job: job,
            actions: StateMapping.actions(life, tab: .job),
            isBusy: isBusy,
            outcome: outcome
        )
    }
}
