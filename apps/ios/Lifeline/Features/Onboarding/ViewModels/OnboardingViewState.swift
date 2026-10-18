import Foundation

/// Onboarding (ADR 0069): Welcome, Problem, Language, What you can do, Try Penny, Pick your student,
/// Building their profile, Their profile, How Penny decides, Their Next Move, then Start.
/// Plain values only. The View never sees contract types (ADR 0011).
struct OnboardingViewState: Equatable, Sendable {
    enum Step: Equatable, Sendable, CaseIterable {
        case welcome
        /// "One app. Every source. One clear decision."
        case problem
        /// Language (ADR 0063): live on tap, then Confirm. Skip keeps the current language.
        case language
        /// "What you can do": 5 explainer rows, nothing tappable.
        case features
        /// "Try Penny": an open Penny chat, not tied to any data.
        case penny
        /// "Pick your student": sample student cards, then upload and manual entry.
        case connect
        case manual
        /// Sign in (kept for a later build; not in the ADR 0069 order).
        case signIn
        /// "Building their profile": 8 stages, each tied to a real call.
        case building
        /// "Their profile".
        case profile
        /// "How Penny decides".
        case howDecides
        /// "Their Next Move", then Start.
        case nextMove
    }

    /// The flow order (ADR 0069). Manual entry and sign in sit beside "Pick your student".
    static let order: [Step] = [.welcome, .problem, .language, .features, .penny, .connect, .building, .profile, .howDecides, .nextMove]

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

    /// One way money arrives, with its amount per period and dates: "£280 a month", "1st of each month".
    struct MoneyInLine: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var amountText: String
        var dates: String?
    }

    /// One built-in sample student (`GET /v1/samples`). Missing fields hide their rows.
    struct SampleCard: Equatable, Sendable, Identifiable {
        var id: String
        /// "Amara Okoye", or the title when the server sends no name.
        var title: String
        /// "Scholarship student" when a name is present.
        var kindText: String?
        /// "19"
        var ageText: String?
        /// Icon id, for example "face-teen-hijab".
        var avatar: String?
        /// "University of Sheffield, Sheffield".
        var placeText: String?
        /// "Scholarship + bursary", or the funding kinds joined.
        var fundingText: String
        var moneyIn: [MoneyInLine] = []
        var housing: String?
        var habitLine: String?
        /// Shown only when the card has no money-in lines.
        var text: String
    }

    /// One "Building their profile" stage.
    struct BuildStage: Equatable, Sendable, Identifiable {
        enum Status: Equatable, Sendable { case waiting, running, done, skipped }
        var id: String
        var label: String
        var status: Status = .waiting
        /// What the call found, for example "412 payments" or "3 bills, 2 subscriptions".
        var detail: String?
    }

    struct Building: Equatable, Sendable {
        var stages: [BuildStage] = []
        /// True when every stage has ended: the "View profile" button shows.
        var isFinished = false
    }

    struct ProfileRow: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var valueText: String
        var detail: String?
    }

    struct SpendSlice: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        /// £ for the chart.
        var amount: Double
        var amountText: String
        /// "36%" of the shown spending.
        var shareText: String = ""
        /// Colour by rank (`ForecastPalette.slice`): 0 green, 1 blue, 2 orange, 3 purple, 4 grey, then light grey.
        var colorIndex: Int = 0
    }

    struct HabitPart: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        /// 0 to 100.
        var value: Int
    }

    /// One of "3 things Penny noticed". Tap shows the evidence (the fact's numbers).
    struct Noticed: Equatable, Sendable, Identifiable {
        var id: String
        var text: String
        /// Icon id for the small visual, for example "subscriptions".
        var icon: String
        var evidence: [ProfileRow]
        /// "From their statement".
        var sourceText: String
    }

    struct Profile: Equatable, Sendable {
        var name: String?
        var subtitle: String?
        var avatar: String?
        var incomes: [MoneyInLine] = []
        var housing: String?
        /// The one period every money block uses: "September" (the last full month) or "October so far".
        var periodText: String?
        var spending: [SpendSlice] = []
        /// "£1,796 in September".
        var spendingTotalText: String?
        /// Bills and subscriptions paid in the same period as the chart. Their total equals the chart's
        /// bills and subscriptions slices.
        var bills: [ProfileRow] = []
        /// "£14 in September". Nil hides it.
        var billsTotalText: String?
        var debts: [ProfileRow] = []
        /// Checked for debts and found none.
        var noDebts = false
        var savingsText: String?
        /// "About 3.8 months of spending".
        var coverText: String?
        var habitOverall: Int?
        var habitParts: [HabitPart] = []
        var noticed: [Noticed] = []
    }

    /// One step of "How Penny decides" (PENNY_V3_BUILD B2, C8): the forecast maths with real numbers and sources.
    struct DecideStep: Equatable, Sendable, Identifiable {
        var id: Int { number }
        var number: Int
        /// "Money now".
        var title: String
        /// "£318", "−£18", "2 Nov · £735".
        var amountText: String
        /// "Your account today". Nil hides it.
        var detail: String?
        /// "Your statement", "Bank of England". Plain names, shown under the step.
        var sources: [String]
    }

    /// "How Penny decides": the forecast steps, then the result.
    struct Decides: Equatable, Sendable {
        /// "Will Eilidh's money last until their next money arrives?"
        var question: String
        var steps: [DecideStep]
        /// "£270 left ÷ 2 weeks". Nil when there is no next money.
        var sumLine: String?
        /// "= £135 a week".
        var resultText: String?
        /// "About £19 a day".
        var dailyText: String?
        /// "You spent £122 a week on average over the last 4 weeks. That's £13 under £135, so you're on track."
        var habitText: String?
        /// "Your statement, 20 Sep to 17 Oct".
        var habitSource: String?
        /// "On track", "Running short".
        var verdict: String
    }

    struct FeatureRow: Equatable, Sendable, Identifiable {
        var id: String
        var title: String
        var text: String
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
            // Month name in the app language, for example "Mar 2027".
            var parts = DateComponents()
            parts.year = dealEndYear
            parts.month = max(1, min(12, dealEndMonth))
            parts.day = 1
            let calendar = Calendar(identifier: .gregorian)
            guard let date = calendar.date(from: parts) else { return String(dealEndYear) }
            return date.formatted(.dateTime.month(.abbreviated).year().locale(FinanceMapping.dateLocale))
        }
    }


    var step: Step = .welcome
    /// The language picked on the language screen (the saved app language until then).
    var language: AppLanguage = .en
    var signIn = SignIn(appleAvailable: false)
    var options: [ConnectOption] = OnboardingViewState.connectOptions
    var manual: Manual
    /// Sample students. Empty while loading (the view shows skeleton cards).
    var samples: [SampleCard] = []
    var samplesLoading = false
    var building = Building()
    var profile: Profile?
    /// The "3 things Penny noticed" row that shows its evidence.
    var expandedNoticedID: String?
    var decides: Decides?
    /// "Their Next Move": the forecast card (B3.1).
    var forecastCard: ForecastCardState?
    var isBusy = false
    /// The Monzo pop-up (sign-in in Safari, approval in the Monzo app, import). Nil: no pop-up.
    var monzoWait: MonzoWait?
    /// The Trading 212 key and secret sheet.
    var trading212 = Trading212Sheet()
    /// Error for the current step, in plain English.
    var errorMessage: String?
    /// Sample data (mock client or a sample student). No badge in onboarding (B4): "Pick your student" shows
    /// the honesty line instead.
    var isSampleData = false

    /// "What you can do" (PENNY_V3_BUILD C4): icon, headline, one line. Explainer only.
    static var featureRows: [FeatureRow] { [
        .init(id: "allMoney", title: L10n.tr("See all your money"), text: L10n.tr("Loan, job, parents, bank and bills in one place.")),
        .init(id: "weekly", title: L10n.tr("Know what you can spend each week"), text: L10n.tr("Penny checks your money lasts until your next money arrives.")),
        .init(id: "maths", title: L10n.tr("See the maths behind it"), text: L10n.tr("Every step and every number, with its source.")),
        .init(id: "penny", title: L10n.tr("Ask Penny"), text: L10n.tr("Short answers about money and student life.")),
        .init(id: "friends", title: L10n.tr("Learn and play with friends"), text: L10n.tr("Short lessons and quizzes. Share habits, never amounts.")),
    ] }

    /// Your own money: Monzo, Trading 212, a statement, or typed numbers. Monzo and Trading 212 show
    /// "Unavailable" when the server is not set up for them.
    static var connectOptions: [ConnectOption] { [
        .init(kind: .monzo, title: L10n.tr("Connect Monzo"), subtitle: L10n.tr("Sign in with Monzo. We only read."), isUnavailable: false),
        .init(kind: .trading212, title: L10n.tr("Connect Trading 212"), subtitle: L10n.tr("Add your investments with an API key."), isUnavailable: false),
        .init(kind: .statement, title: L10n.tr("Upload a statement"), subtitle: L10n.tr("Monzo or Revolut CSV, or a PDF. Max 5 MB."), isUnavailable: false),
        .init(kind: .manual, title: L10n.tr("Enter your numbers"), subtitle: L10n.tr("Takes about 2 minutes"), isUnavailable: false),
    ] }
}

/// Where `OnboardingScreen` opens. The router opens `.connect` from Money and You.
enum OnboardingStep: String, Hashable, Sendable {
    case welcome
    case connect
    /// Only "Enter your numbers", from the connections screen. Saving closes it.
    case manual
}

/// What the onboarding View can ask for.
/// The Trading 212 sheet (key and secret). The secret is only ever held in the sheet while it is open.
struct Trading212Sheet: Equatable, Sendable {
    var isPresented = false
    var isBusy = false
    var errorMessage: String?
}

enum MonzoWait: Equatable, Sendable {
    case signingIn, approving, importing
    case failed(String)
}

struct OnboardingActions {
    var onNext: () -> Void = {}
    var onBack: () -> Void = {}
    /// Skip on Language (keeps the current language), Try Penny and How Penny decides.
    var onSkip: () -> Void = {}
    var onSignInWithApple: () -> Void = {}
    var onContinueWithoutAccount: () -> Void = {}
    var onConnect: (OnboardingViewState.ConnectOption.Kind) -> Void = { _ in }
    var onManualChange: (OnboardingViewState.Manual) -> Void = { _ in }
    var onAddCost: () -> Void = {}
    var onRemoveCost: (Int) -> Void = { _ in }
    var onUseLocation: () -> Void = {}
    var onSaveManual: () -> Void = {}
    var onPickLanguage: (AppLanguage) -> Void = { _ in }
    var onConfirmLanguage: () -> Void = {}
    var onPickSample: (String) -> Void = { _ in }
    var onToggleIncome: (String) -> Void = { _ in }
    var onToggleDebt: (String) -> Void = { _ in }
    /// "3 things Penny noticed": show or hide one row's evidence.
    var onToggleNoticed: (String) -> Void = { _ in }
    var onFinish: () -> Void = {}
    /// "See the maths" on the forecast card: back to "How Penny decides".
    var onSeeMaths: () -> Void = {}
    /// "Ask Penny" on the forecast card: Penny with the forecast loaded.
    var onAskPenny: () -> Void = {}
    var onDismissError: () -> Void = {}
    /// Trading 212 sheet: submit the key and secret, or close it.
    var onSubmitTrading212: (_ key: String, _ secret: String) -> Void = { _, _ in }
    var onCloseTrading212: () -> Void = {}
    /// Monzo pop-up: open Safari again, cancel or close, try again.
    var onMonzoReopen: () -> Void = {}
    var onMonzoCancel: () -> Void = {}
    var onMonzoRetry: () -> Void = {}

    static var noop: OnboardingActions { OnboardingActions() }
}
