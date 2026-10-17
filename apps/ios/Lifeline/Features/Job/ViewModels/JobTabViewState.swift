import Foundation

struct JobTabViewState: Equatable, Sendable {
    struct JobInfo: Equatable, Sendable {
        var title: String
        var employer: String?
        var annualIncome: Double
        var yearsInRole: Int
        /// Plain English employer status, for example "Employer in trouble".
        var employerStatus: String?
        var employerAtRisk: Bool
    }

    /// Nil when the character has no job.
    var job: JobInfo?
    var actions: [ActionItemState]
    var isBusy: Bool
    var outcome: OutcomeState?
}
