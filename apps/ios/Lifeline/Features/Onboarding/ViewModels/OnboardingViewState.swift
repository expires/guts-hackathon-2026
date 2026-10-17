import Foundation

/// Onboarding (ADR 0029): welcome (3 pages), sign in, connect your money, importing, Next Move reveal, 3 tips.
/// Plain values only. The View never sees contract types (ADR 0011).
struct OnboardingViewState: Equatable, Sendable {
    enum Step: Equatable, Sendable {
        case welcome(page: Int)
        case signIn
        case connect
        /// "Use a sample statement": pick one of the student cards.
        case samples
        case manual
        case importing
        case reveal
        case tips
    }

    struct WelcomePage: Equatable, Sendable, Identifiable {
        var id: Int
        var title: String
        var text: String
        var art: Art
        enum Art: Equatable, Sendable { case penny, why, test }
    }

    struct SignIn: Equatable, Sendable {
        /// The app has the Sign in with Apple capability (checked at run time).
        var appleAvailable: Bool
        /// Shown under the buttons, for example after a fallback to demo sign-in.
        var note: String?
    }

    /// One way to connect your money.
    struct ConnectOption: Equatable, Sendable, Identifiable {
        enum Kind: String, Equatable, Sendable { case sample, monzo, trading212, statement, manual }
        var kind: Kind
        var title: String
        var subtitle: String
        var isUnavailable: Bool
        var id: String { kind.rawValue }
    }

    /// One built-in sample student (`GET /v1/finance/samples`).
    struct SampleCard: Equatable, Sendable, Identifiable {
        var id: String
        var title: String
        var text: String
        /// "Scholarship · Bursary"
        var fundingText: String
        /// "3 months of payments"
        var monthsText: String
    }

    /// One way money arrives (student form). Off until the user turns it on.
    struct IncomeRow: Equatable, Sendable, Identifiable {
        enum Kind: String, Equatable, Sendable, CaseIterable {
            case maintenanceLoan = "maintenance_loan", scholarship, bursary, grant, family
            case partTimeJob = "part_time_job", salary
            var label: String {
                switch self {
                case .maintenanceLoan: "Maintenance loan"
                case .scholarship: "Scholarship"
                case .bursary: "Bursary"
                case .grant: "Grant"
                case .family: "Parents or family"
                case .partTimeJob: "Part-time job"
                case .salary: "Salary"
                }
            }
            /// The usual schedule. The user can change it (for example monthly loan payments in Scotland).
            var defaultSchedule: Schedule {
                switch self {
                case .maintenanceLoan, .scholarship, .bursary, .grant: .termly
                case .family, .partTimeJob, .salary: .monthly
                }
            }
        }
        enum Schedule: String, Equatable, Sendable, CaseIterable {
            case weekly, monthly, termly, yearly
            var label: String { rawValue.capitalized }
            /// Payments a year, to work out a monthly figure.
            var perYear: Double {
                switch self {
                case .weekly: 52
                case .monthly: 12
                case .termly: 3
                case .yearly: 1
                }
            }
        }
        var kind: Kind
        var isOn = false
        /// £ per payment.
        var amount: Double = 0
        var schedule: Schedule
        var id: String { kind.rawValue }
    }

    /// A debt (student form). Off until the user turns it on.
    struct DebtRow: Equatable, Sendable, Identifiable {
        enum Kind: String, Equatable, Sendable, CaseIterable {
            case card, overdraft, bnpl
            var label: String {
                switch self {
                case .card: "Credit card"
                case .overdraft: "Overdraft"
                case .bnpl: "Buy now, pay later (Klarna)"
                }
            }
        }
        var kind: Kind
        var isOn = false
        var balance: Double = 0
        var id: String { kind.rawValue }
    }

    enum LoanPlan: String, Equatable, Sendable, CaseIterable {
        case plan1 = "plan_1", plan2 = "plan_2", plan4 = "plan_4", plan5 = "plan_5", postgraduate, none
        var label: String {
            switch self {
            case .plan1: "Plan 1"
            case .plan2: "Plan 2"
            case .plan4: "Plan 4 (Scotland)"
            case .plan5: "Plan 5"
            case .postgraduate: "Postgraduate"
            case .none: "No loan"
            }
        }
    }

    struct CostRow: Equatable, Sendable, Identifiable {
        var id: Int
        var name: String
        var monthlyAmount: Double
    }

    /// "Enter your numbers". Every value is what the user typed.
    struct Manual: Equatable, Sendable {
        /// Student or working (ADR 0049). Students list their income sources instead of take-home pay.
        var isStudent = true
        /// Nil until the user sets it.
        var age: Int?
        var incomes: [IncomeRow] = IncomeRow.Kind.allCases.map { .init(kind: $0, schedule: $0.defaultSchedule) }
        var loanPlan: LoanPlan?
        var debts: [DebtRow] = DebtRow.Kind.allCases.map { .init(kind: $0) }
        var postcode = ""
        var housing: Housing = .rent
        var monthlyRent: Double = 0
        var mortgageBalance: Double = 0
        var mortgageRatePercent: Double = 0
        var dealEndYear: Int
        var dealEndMonth: Int
        var dealEndYears: ClosedRange<Int>
        var monthlyTakeHome: Double = 0
        var savings: Double = 0
        var costs: [CostRow] = []
        /// "Leeds, from your location" or "Location is not set up yet."
        var locationNote: String?
        var isLocating = false
        /// Plain English problems that block "Save my numbers".
        var problems: [String] = []

        enum Housing: String, Equatable, Sendable, CaseIterable {
            case rent, own, mortgage, parents
            var label: String {
                switch self {
                case .rent: "I rent"
                case .own: "I own it outright"
                case .mortgage: "Mortgage"
                case .parents: "With family"
                }
            }
        }

        var dealEndText: String {
            let months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            return "\(months[max(0, min(11, dealEndMonth - 1))]) \(String(dealEndYear))"
        }
    }

    struct Stage: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var done: Bool
    }

    /// "Importing your history".
    struct Importing: Equatable, Sendable {
        var title: String
        var stages: [Stage] = []
        /// Stages shown so far (the view animates them in one by one).
        var shownCount = 0
        /// "412 payments, 1 Apr 2026 to 16 Oct 2026". Nil until the import returns.
        var summary: String?
        var warnings: [String] = []
        var isFinished = false
    }

    /// The Next Move reveal: the engine's top move.
    struct Reveal: Equatable, Sendable {
        var action: String
        var headline: String
        var impactAmountText: String
        var impactCaption: String
        var confidenceWord: String
        var confidenceFilled: Int
        var confidenceLabel: String
        var isSampleData: Bool
    }

    struct Tip: Equatable, Sendable, Identifiable {
        var id: String
        var number: Int
        var text: String
    }

    var step: Step = .welcome(page: 0)
    var pages: [WelcomePage] = OnboardingViewState.welcomePages
    var signIn = SignIn(appleAvailable: false)
    var options: [ConnectOption] = OnboardingViewState.connectOptions
    var manual: Manual
    /// Sample students. Empty while loading (the view shows skeleton rows).
    var samples: [SampleCard] = []
    var samplesLoading = false
    var importing = Importing(title: "Importing your history")
    var reveal: Reveal?
    var tips: [Tip] = []
    var isBusy = false
    /// Error for the current step, in plain English.
    var errorMessage: String?
    /// Sample data (mock client): show the "Mock data" badge.
    var isSampleData = false

    static let welcomePages: [WelcomePage] = [
        .init(id: 0, title: Brand.tagline, text: "\(Brand.productName) uses real UK data to show what your money choices do over the years.", art: .penny),
        .init(id: 1, title: "One next move.", text: "You get one clear money move, with the evidence and how sure we are.", art: .why),
        .init(id: 2, title: "Test it first.", text: "Play the move through real years, like the 2022 price rises, and see what would have happened.", art: .test),
    ]

    /// Bank and broker connections are cut (ADR 0046): statement upload and manual entry only.
    static let connectOptions: [ConnectOption] = [
        .init(kind: .sample, title: "Use a sample statement", subtitle: "Pick one of 4 students. Shown as sample data.", isUnavailable: false),
        .init(kind: .statement, title: "Upload a statement", subtitle: "Monzo or Revolut CSV, or a PDF. Max 5 MB.", isUnavailable: false),
        .init(kind: .manual, title: "Enter your numbers", subtitle: "Takes about 2 minutes", isUnavailable: false),
    ]
}

/// Where `OnboardingScreen` opens. The router opens `.connect` from Money and You.
enum OnboardingStep: String, Hashable, Sendable {
    case welcome
    case connect
}

/// What the onboarding View can ask for.
struct OnboardingActions {
    var onNext: () -> Void = {}
    var onBack: () -> Void = {}
    var onSkipWelcome: () -> Void = {}
    var onSignInWithApple: () -> Void = {}
    var onContinueWithoutAccount: () -> Void = {}
    var onConnect: (OnboardingViewState.ConnectOption.Kind) -> Void = { _ in }
    var onManualChange: (OnboardingViewState.Manual) -> Void = { _ in }
    var onAddCost: () -> Void = {}
    var onRemoveCost: (Int) -> Void = { _ in }
    var onUseLocation: () -> Void = {}
    var onSaveManual: () -> Void = {}
    var onPickSample: (String) -> Void = { _ in }
    var onToggleIncome: (String) -> Void = { _ in }
    var onToggleDebt: (String) -> Void = { _ in }
    var onStageShown: () -> Void = {}
    var onFinish: () -> Void = {}
    var onDismissError: () -> Void = {}

    static var noop: OnboardingActions { OnboardingActions() }
}
