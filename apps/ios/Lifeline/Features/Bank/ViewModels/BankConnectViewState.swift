import Foundation

struct BankConnectViewState: Equatable, Sendable {
    enum Step: Equatable, Sendable {
        case intro
        case connecting
        case connected
        case failed(ErrorViewState)
    }

    struct Summary: Equatable, Sendable {
        var accounts: Int
        var annualIncome: Double
        var savings: Double
        var housingLabel: String
        var regionLabel: String
    }

    var step: Step
    var providerName: String
    /// Freshness of the bank data. `.mock` shows "sample data".
    var status: DataStatus?
    var summary: Summary?
    var privacyNote: String
}

struct BankConnectActions {
    var onConnect: @MainActor () -> Void = {}
    var onUseProfile: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
