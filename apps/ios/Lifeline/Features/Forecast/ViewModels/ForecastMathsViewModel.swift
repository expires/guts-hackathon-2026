import Foundation
import Observation

/// "The maths" (B3.3, canvas 3): 4 steps with sources, the buffer buttons, the sum, habits, stress test.
struct ForecastMathsState: Equatable, Sendable {
    struct Step: Equatable, Sendable, Identifiable {
        var id: Int { number }
        var number: Int
        var title: String
        /// "£318", "−£18", "2 Nov · £735".
        var amountText: String
        /// "Your account today · your statement".
        var detail: String
        /// Buffer step only: shows the 0 to 20% buttons.
        var isBuffer = false
    }

    struct Sum: Equatable, Sendable {
        /// "£270 left ÷ 2 weeks".
        var line: String
        /// "= £135 a week".
        var result: String
        /// "About £19 a day". Nil when the result is already per day.
        var daily: String?
    }

    struct Habits: Equatable, Sendable {
        var text: String
        /// "Your statement, 20 Sep to 17 Oct".
        var source: String?
    }

    enum Stress: Equatable, Sendable {
        case idle
        case loading
        case result(text: String, source: String, stillOK: Bool)
        case failed(String)
    }

    var phase: LoadPhase = .loading(.standard)
    /// "How Penny got £135 a week."
    var intro: String = ""
    var steps: [Step] = []
    static let bufferOptions = [0, 5, 10, 15, 20]
    var bufferPct: Int = 10
    /// True while a buffer preview loads or saves.
    var isUpdatingBuffer = false
    /// "Couldn't save your buffer. Try again." Nil when fine.
    var bufferError: String?
    var sum: Sum?
    var habits: Habits?
    var stress: Stress = .idle
    /// No next money: no sum or buffer to show.
    var hasBudget: Bool { sum != nil }

    static func make(_ forecast: Forecast) -> ForecastMathsState {
        var state = ForecastMathsState(phase: .ready)
        let budget = forecast.state != .noNextMoney && forecast.nextMoneyIfAny != nil && forecast.days > 0
        state.bufferPct = forecast.bufferPct.rawValue
        let until = forecast.isUntilNextMoney
        let nextShort = forecast.nextMoneyIfAny.map { ForecastText.shortDate($0.date) } ?? ""
        state.intro = !budget || forecast.hasNothingToSpend
            ? L10n.tr("How Penny checks your money.")
            : until
            ? L10n.tr("How Penny got \(ForecastText.whole(forecast.moneyToSpend)) until \(nextShort).")
            : L10n.tr("How Penny got \(ForecastText.whole(forecast.perWeek)) a week.")
        func step(_ id: Components.Schemas.ForecastStep.IdPayload) -> Components.Schemas.ForecastStep? {
            forecast.steps.first { $0.id == id }
        }
        func detail(_ step: Components.Schemas.ForecastStep?) -> String {
            guard let step else { return "" }
            let sources = (step.sources ?? []).map(\.label)
            return ([step.text] + sources).filter { !$0.isEmpty }.joined(separator: " · ")
        }
        // Step 1 with expected income: "Money now £318 + expected before 2 Nov £40".
        var moneyDetail = detail(step(.moneyNow))
        if forecast.incomeExpectedTotal > 0 {
            let before = forecast.nextMoneyIfAny.map { ForecastText.shortDate($0.date) } ?? ""
            let line = L10n.tr("Money now \(ForecastText.whole(forecast.moneyNow)) + expected before \(before) \(ForecastText.whole(forecast.incomeExpectedTotal))")
            moneyDetail = [line, moneyDetail].filter { !$0.isEmpty }.joined(separator: " · ")
        }
        state.steps = [
            Step(number: 1, title: step(.moneyNow)?.title ?? L10n.tr("Money now"), amountText: ForecastText.whole(forecast.moneyAvailable), detail: moneyDetail),
            Step(number: 2, title: step(.bills)?.title ?? L10n.tr("Bills before your next money"), amountText: ForecastText.minusWhole(forecast.billsTotal), detail: detail(step(.bills))),
            Step(number: 3, title: step(.buffer)?.title ?? L10n.tr("Safety buffer, \(forecast.bufferPct.rawValue)%"), amountText: ForecastText.minusWhole(forecast.bufferAmount), detail: detail(step(.buffer)), isBuffer: true),
            Step(
                number: 4, title: L10n.tr("Next money"),
                amountText: forecast.nextMoneyIfAny.map { "\(ForecastText.shortDate($0.date)) · \(ForecastText.whole($0.amount))" } ?? L10n.tr("Not found"),
                detail: forecast.nextMoneyIfAny?.source.label ?? L10n.tr("No regular money coming in found in your statement")
            ),
        ]
        if budget, forecast.hasNothingToSpend {
            state.sum = Sum(line: L10n.tr("Bills and the buffer are more than your money now."), result: forecast.budgetLine, daily: nil)
        } else if budget, until {
            state.sum = Sum(
                line: L10n.tr("\(ForecastText.whole(forecast.moneyToSpend)) left ÷ \(forecast.days) days"),
                result: L10n.tr("= \(ForecastText.whole(forecast.perDay)) a day"),
                daily: nil
            )
        } else if budget {
            let spend = forecast.moneyAvailable - forecast.billsTotal - forecast.bufferAmount
            state.sum = Sum(
                line: L10n.tr("\(ForecastText.whole(spend)) left ÷ \(ForecastText.weeks(forecast.days))"),
                result: L10n.tr("= \(ForecastText.whole(forecast.perWeek)) a week"),
                daily: L10n.tr("About \(ForecastText.whole(forecast.perDay)) a day")
            )
        }
        state.habits = habits(forecast)
        if let stress = forecast.stress {
            state.stress = .result(text: stress.text, source: stress.source.label, stillOK: stress.state == .onTrack)
        }
        return state
    }

    static func habits(_ forecast: Forecast) -> Habits? {
        guard !forecast.usualWeeks.isEmpty else { return nil }
        let count = forecast.usualWeeks.count
        let first: String
        let second: String
        if forecast.isUntilNextMoney {
            // Fewer than 14 days: compare a day with a day.
            let usual = ForecastText.whole(forecast.usualDaily)
            let daily = ForecastText.whole(forecast.perDay)
            let gap = ForecastText.whole(abs(forecast.perDay.rounded() - forecast.usualDaily.rounded()))
            first = L10n.tr("You spent \(usual) a day on average over the last \(count) weeks.")
            second = switch forecast.state {
            case .onTrack: L10n.tr("That's \(gap) under \(daily) a day, so you're on track.")
            case .runningShort: L10n.tr("That's \(gap) over \(daily) a day, so at this pace you run short.")
            case .noNextMoney: ""
            }
        } else {
            let usual = ForecastText.whole(forecast.usualWeekly)
            let weekly = ForecastText.whole(forecast.perWeek)
            let gap = ForecastText.whole(abs(forecast.perWeek.rounded() - forecast.usualWeekly.rounded()))
            first = L10n.tr("You spent \(usual) a week on average over the last \(count) weeks.")
            second = switch forecast.state {
            case .onTrack: L10n.tr("That's \(gap) under \(weekly), so you're on track.")
            case .runningShort: L10n.tr("That's \(gap) over \(weekly), so at this pace you run short.")
            case .noNextMoney: ""
            }
        }
        let range = forecast.usualWeeks.first.flatMap { first in
            forecast.usualWeeks.last.map { last in
                L10n.tr("Your statement, \(ForecastText.shortDate(first.start)) to \(ForecastText.shortDate(last.end))")
            }
        }
        return Habits(text: [first, second].filter { !$0.isEmpty }.joined(separator: " "), source: range)
    }
}

struct ForecastMathsActions {
    var onBack: @MainActor () -> Void = {}
    var onBuffer: @MainActor (Int) -> Void = { _ in }
    var onDetail: @MainActor () -> Void = {}
    var onStress: @MainActor () -> Void = {}
    var onAskPenny: @MainActor () -> Void = {}
    /// "Ask Penny 'what if...'": Penny opens with the forecast loaded and no question sent.
    var onAskWhatIf: @MainActor () -> Void = {}
    var onRetry: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}

/// Loads the forecast (cached first) and handles buffer changes: preview with `buffer_pct`, then save with PUT.
@MainActor
@Observable
final class ForecastMathsViewModel {
    private let client: any LifelineClient
    private(set) var forecast: Forecast?
    private var phase: LoadPhase = .loading(.standard)
    private var bufferPct: Int?
    private var isUpdatingBuffer = false
    private var bufferError: String?
    private var stress: ForecastMathsState.Stress = .idle
    /// Every buffer change bumps this, so a slow older preview never overwrites a newer one.
    private var bufferGeneration = 0

    /// A saved buffer changed the forecast. Money home shows the new card.
    @ObservationIgnored var onForecastChanged: @MainActor (Forecast) -> Void = { _ in }
    @ObservationIgnored var onBack: @MainActor () -> Void = {}
    @ObservationIgnored var onDetail: @MainActor () -> Void = {}
    @ObservationIgnored var onAskPenny: @MainActor () -> Void = {}
    @ObservationIgnored var onAskWhatIf: @MainActor () -> Void = {}

    init(client: any LifelineClient, forecast: Forecast? = nil) {
        self.client = client
        if let forecast { show(forecast) }
    }

    var state: ForecastMathsState {
        guard let forecast else { return ForecastMathsState(phase: phase) }
        var state = ForecastMathsState.make(forecast)
        if let bufferPct { state.bufferPct = bufferPct }
        state.isUpdatingBuffer = isUpdatingBuffer
        state.bufferError = bufferError
        if stress != .idle || forecast.stress == nil { state.stress = stress }
        return state
    }

    var actions: ForecastMathsActions {
        ForecastMathsActions(
            onBack: { [weak self] in self?.onBack() },
            onBuffer: { [weak self] pct in Task { await self?.selectBuffer(pct) } },
            onDetail: { [weak self] in self?.onDetail() },
            onStress: { [weak self] in Task { await self?.runStress() } },
            onAskPenny: { [weak self] in self?.onAskPenny() },
            onAskWhatIf: { [weak self] in self?.onAskWhatIf() },
            onRetry: { [weak self] in Task { await self?.load() } }
        )
    }

    func show(_ forecast: Forecast) {
        self.forecast = forecast
        phase = .ready
    }

    func load() async {
        if forecast == nil { phase = .loading(.standard) }
        do {
            try await client.load(CachedOps.forecast) { [weak self] value in
                guard let self, !isUpdatingBuffer else { return }
                show(value)
            }
        } catch {
            if forecast == nil { phase = .failed(.from(APIError.map(error))) }
        }
    }

    /// Previews the forecast with `pct` at once, then stores it. A failed save goes back to the saved value.
    func selectBuffer(_ pct: Int) async {
        guard ForecastMathsState.bufferOptions.contains(pct), pct != (bufferPct ?? forecast?.bufferPct.rawValue) else { return }
        let previous = forecast
        bufferGeneration += 1
        let generation = bufferGeneration
        bufferPct = pct
        bufferError = nil
        isUpdatingBuffer = true
        stress = .idle
        defer { if generation == bufferGeneration { isUpdatingBuffer = false } }
        do {
            let preview = try await client.forecast(bufferPct: pct, stress: nil)
            guard generation == bufferGeneration else { return }
            show(preview)
            _ = try await client.setForecastSettings(bufferPct: pct)
            guard generation == bufferGeneration else { return }
            // The cached forecast now uses the new buffer.
            await client.refresh(CachedOps.forecast)
            onForecastChanged(preview)
        } catch {
            guard generation == bufferGeneration else { return }
            if let previous { show(previous) }
            bufferPct = previous?.bufferPct.rawValue
            bufferError = L10n.tr("Couldn't save your buffer. Try again.")
        }
    }

    /// "What if prices rose like in 2022?": reruns with 2022 inflation and shows the result here.
    func runStress() async {
        guard stress != .loading else { return }
        stress = .loading
        do {
            let result = try await client.forecast(bufferPct: bufferPct ?? forecast?.bufferPct.rawValue, stress: 2022)
            guard let test = result.stress else {
                stress = .failed(L10n.tr("Couldn't run this check. Try again."))
                return
            }
            stress = .result(text: test.text, source: test.source.label, stillOK: test.state == .onTrack)
        } catch {
            stress = .failed(L10n.tr("Couldn't run this check. Try again."))
        }
    }
}

/// "Detailed breakdown" (B3.4, canvas 3b): every account, bill, date and week, in pence, with a source per block.
struct ForecastBreakdownState: Equatable, Sendable {
    struct Row: Equatable, Sendable, Identifiable {
        var id: Int
        var label: String
        var note: String?
        var value: String
        var isTotal = false
    }

    struct Section: Equatable, Sendable, Identifiable {
        var id: Int { number }
        var number: Int
        var title: String
        var rows: [Row]
        var source: String
    }

    /// The pence behind the rows, so tests and the screen can check that every sum adds up.
    struct Sums: Equatable, Sendable {
        var accountsCounted: Int
        var moneyNow: Int
        var expectedListed: Int
        var expectedTotal: Int
        var billsListed: Int
        var billsTotal: Int
        var buffer: Int
        /// money now + expected income − bills − buffer.
        var toSpend: Int
        var usualWeeks: [Int]
        var usualWeekly: Int

        var moneyAddsUp: Bool { accountsCounted == moneyNow && expectedListed == expectedTotal }
        var billsAddUp: Bool { billsListed == billsTotal }
    }

    /// "Every number behind £135 a week, line by line."
    var intro: String
    var sections: [Section]
    /// "Your most expensive week was £131. Even at that pace, you still make it to 2 November."
    var closing: String?
    var closingIsGood: Bool
    var sums: Sums

    static func make(_ forecast: Forecast) -> ForecastBreakdownState {
        let p = ForecastText.toPence
        let money = ForecastText.pence
        let minus = ForecastText.minusPence
        let next = forecast.nextMoneyIfAny
        let hasNext = forecast.state != .noNextMoney && next != nil && forecast.days > 0
        let until = forecast.isUntilNextMoney
        let nextDate = next.map { ForecastText.longDate($0.date) } ?? ""
        let sums = Sums(
            accountsCounted: forecast.accounts.filter(\.counted).reduce(0) { $0 + p($1.balance) },
            moneyNow: p(forecast.moneyNow),
            expectedListed: forecast.incomeExpected.reduce(0) { $0 + p($1.amount) },
            expectedTotal: p(forecast.incomeExpectedTotal),
            billsListed: forecast.bills.reduce(0) { $0 + p($1.amount) },
            billsTotal: p(forecast.billsTotal),
            buffer: p(forecast.bufferAmount),
            toSpend: p(forecast.moneyNow) + p(forecast.incomeExpectedTotal) - p(forecast.billsTotal) - p(forecast.bufferAmount),
            usualWeeks: forecast.usualWeeks.map { p($0.amount) },
            usualWeekly: p(forecast.usualWeekly)
        )
        let toSpend = Double(sums.toSpend) / 100
        let left = Double(sums.moneyNow + sums.expectedTotal - sums.billsTotal) / 100
        var sections: [Section] = []

        // 1. Money now
        var rows = forecast.accounts.enumerated().map { index, account in
            Row(id: index, label: account.name, note: account.counted ? nil : notCounted(account.kind), value: money(account.balance))
        }
        for income in forecast.incomeExpected.sorted(by: { $0.date < $1.date }) {
            rows.append(Row(
                id: rows.count, label: income.label,
                note: L10n.tr("Expected \(ForecastText.shortDate(income.date))") + " · " + income.source.label,
                value: money(income.amount)
            ))
        }
        rows.append(Row(id: rows.count, label: L10n.tr("Counted"), value: money(forecast.moneyAvailable), isTotal: true))
        let asOf = ForecastText.shortDate(forecast.today)
        var moneySource = L10n.tr("Your statement, balance at the end of \(asOf)")
        if !forecast.incomeExpected.isEmpty {
            moneySource += ". " + L10n.tr("Expected income before your next money is added.")
        }
        sections.append(Section(number: 1, title: L10n.tr("Money now"), rows: rows, source: moneySource))

        // 2. Bills before your next money
        rows = forecast.bills.sorted { $0.dueDate < $1.dueDate }.enumerated().map { index, bill in
            Row(id: index, label: bill.name, note: L10n.tr("Due \(ForecastText.shortDate(bill.dueDate))"), value: money(bill.amount))
        }
        if rows.isEmpty { rows.append(Row(id: 0, label: L10n.tr("No bills in this time"), value: money(0))) }
        rows.append(Row(id: rows.count, label: L10n.tr("Total"), value: minus(forecast.billsTotal), isTotal: true))
        sections.append(Section(number: 2, title: L10n.tr("Bills before your next money"), rows: rows, source: L10n.tr("Bills found as repeat payments in your statement")))

        // 3. Safety buffer
        sections.append(Section(number: 3, title: L10n.tr("Safety buffer"), rows: [
            Row(id: 0, label: L10n.tr("Left after bills"), value: money(left)),
            Row(id: 1, label: L10n.tr("Your buffer"), note: forecast.bufferPct == ._10 ? L10n.tr("Recommended. Change it on the previous screen or in Settings") : L10n.tr("Change it on the previous screen or in Settings"), value: "\(forecast.bufferPct.rawValue)%"),
            Row(id: 2, label: L10n.tr("Buffer"), value: minus(forecast.bufferAmount), isTotal: true),
        ], source: L10n.tr("Your setting")))

        // 4. Time until your next money
        if hasNext, let next {
            let from = ForecastText.shortDate(ForecastText.addDays(1, to: forecast.today))
            let to = ForecastText.shortDate(ForecastText.addDays(-1, to: next.date))
            let weeks = (Double(forecast.days) / 7).formatted(.number.precision(.fractionLength(1)).locale(Locale(identifier: "en_GB")))
            sections.append(Section(number: 4, title: L10n.tr("Time until your next money"), rows: [
                Row(id: 0, label: next.label, note: L10n.tr("Expected \(ForecastText.shortDate(next.date))"), value: money(next.amount)),
                Row(id: 1, label: L10n.tr("Days to cover"), note: L10n.tr("\(from) to \(to) (today's spending is already in)"), value: "\(forecast.days)"),
                Row(id: 2, label: L10n.tr("Weeks"), value: weeks, isTotal: true),
            ], source: next.source.label))

            // 5. The sum
            var sumNote = money(forecast.moneyNow)
            if forecast.incomeExpectedTotal > 0 { sumNote += " + " + money(forecast.incomeExpectedTotal) }
            sumNote += " \u{2212} \(money(forecast.billsTotal)) \u{2212} \(money(forecast.bufferAmount))"
            var sumRows = [
                Row(id: 0, label: L10n.tr("Money to spend"), note: sumNote, value: money(toSpend), isTotal: until),
                Row(id: 1, label: L10n.tr("Per day"), note: L10n.tr("\(money(toSpend)) ÷ \(forecast.days) days"), value: money(forecast.perDay), isTotal: until),
            ]
            if !until {
                sumRows.append(Row(id: 2, label: L10n.tr("Per week"), note: L10n.tr("\(money(toSpend)) ÷ \(forecast.days) days × 7"), value: money(forecast.perWeek), isTotal: true))
            }
            let rounding = until
                ? L10n.tr("Rounded to \(ForecastText.whole(toSpend)) until \(ForecastText.shortDate(next.date)) and \(ForecastText.whole(forecast.perDay)) a day on the card")
                : L10n.tr("Rounded to \(ForecastText.whole(forecast.perWeek)) a week and \(ForecastText.whole(forecast.perDay)) a day on the card")
            sections.append(Section(number: 5, title: L10n.tr("The sum"), rows: sumRows, source: rounding))
        }

        // 6. Your usual spending
        rows = forecast.usualWeeks.enumerated().map { index, week in
            Row(id: index, label: weekRange(week.start, week.end), value: money(week.amount))
        }
        rows.append(Row(id: rows.count, label: L10n.tr("Average"), value: L10n.tr("\(money(forecast.usualWeekly)) a week"), isTotal: true))
        if hasNext, until {
            rows.append(Row(id: rows.count, label: L10n.tr("Average a day"), value: money(forecast.usualDaily)))
            let gap = abs(forecast.perDay - forecast.usualDaily)
            let under = forecast.usualDaily <= forecast.perDay
            rows.append(Row(
                id: rows.count, label: L10n.tr("Compared with \(money(forecast.perDay)) a day"),
                note: under ? L10n.tr("So you are on track") : L10n.tr("So at this pace you run short"),
                value: under ? L10n.tr("\(money(gap)) under") : L10n.tr("\(money(gap)) over"), isTotal: true
            ))
        } else if hasNext {
            let gap = abs(forecast.perWeek - forecast.usualWeekly)
            let under = forecast.usualWeekly <= forecast.perWeek
            rows.append(Row(
                id: rows.count, label: L10n.tr("Compared with \(money(forecast.perWeek))"),
                note: under ? L10n.tr("So you are on track") : L10n.tr("So at this pace you run short"),
                value: under ? L10n.tr("\(money(gap)) under") : L10n.tr("\(money(gap)) over"), isTotal: true
            ))
        }
        var usualSource = L10n.tr("Your statement. Not counted: rent, bills, transfers to savings")
        if forecast.cpiAdjusted == true, let note = forecast.cpiNote { usualSource += ". " + note }
        sections.append(Section(number: hasNext ? 6 : 4, title: L10n.tr("Your usual spending"), rows: rows, source: usualSource))

        // 7. Spare, or the run-out day
        if hasNext, until, let spare = forecast.spare, forecast.state == .onTrack {
            let daily = forecast.perDay - forecast.usualDaily
            sections.append(Section(number: 7, title: L10n.tr("Spare on \(nextDate)"), rows: [
                Row(id: 0, label: "\(money(forecast.perDay)) \u{2212} \(money(forecast.usualDaily))", value: L10n.tr("\(money(daily)) a day")),
                Row(id: 1, label: L10n.tr("× \(forecast.days) days"), value: L10n.tr("About \(money(spare)) spare"), isTotal: true),
            ], source: L10n.tr("If you keep to your usual pace")))
        } else if hasNext, let spare = forecast.spare, forecast.state == .onTrack {
            let weekly = forecast.perWeek - forecast.usualWeekly
            sections.append(Section(number: 7, title: L10n.tr("Spare on \(nextDate)"), rows: [
                Row(id: 0, label: "\(money(forecast.perWeek)) \u{2212} \(money(forecast.usualWeekly))", value: L10n.tr("\(money(weekly)) a week")),
                Row(id: 1, label: L10n.tr("× \(ForecastText.weeks(forecast.days))"), value: L10n.tr("About \(money(spare)) spare"), isTotal: true),
            ], source: L10n.tr("If you keep to your usual pace")))
        } else if hasNext, let runOut = forecast.runOutDate {
            let daysLeft = ForecastText.days(from: forecast.today, to: runOut)
            sections.append(Section(number: 7, title: L10n.tr("When the money runs out"), rows: [
                Row(id: 0, label: L10n.tr("Left after bills"), value: money(left)),
                Row(id: 1, label: L10n.tr("Your usual spending a day"), value: money(forecast.usualDaily)),
                Row(id: 2, label: L10n.tr("\(money(left)) ÷ \(money(forecast.usualDaily))"), note: L10n.tr("Whole days from today"), value: L10n.tr("\(daysLeft) days")),
                Row(id: 3, label: L10n.tr("Runs out"), value: ForecastText.longDate(runOut), isTotal: true),
            ], source: L10n.tr("If you keep to your usual pace")))
        }

        // Closing check: the most expensive week, at the same pace to the next money.
        var closing: String?
        var good = true
        if hasNext, let worst = forecast.usualWeeks.map(\.amount).max() {
            let need = worst / 7 * Double(forecast.days)
            good = need <= left
            closing = good
                ? L10n.tr("Your most expensive week was \(ForecastText.whole(worst)). Even at that pace, you still make it to \(nextDate).")
                : L10n.tr("Your most expensive week was \(ForecastText.whole(worst)). At that pace, your money would not last to \(nextDate).")
        }
        return ForecastBreakdownState(
            intro: hasNext && until
                ? L10n.tr("Every number behind \(ForecastText.whole(forecast.moneyToSpend)) until \(nextDate), line by line.")
                : hasNext
                ? L10n.tr("Every number behind \(ForecastText.whole(forecast.perWeek)) a week, line by line.")
                : L10n.tr("Every number Penny used, line by line."),
            sections: sections, closing: closing, closingIsGood: good, sums: sums
        )
    }

    static func notCounted(_ kind: Components.Schemas.ForecastAccount.KindPayload) -> String {
        switch kind {
        case .savings: L10n.tr("Not counted: savings stay put")
        case .credit: L10n.tr("Not counted: credit card")
        default: L10n.tr("Not counted")
        }
    }

    /// "20 to 26 Sep" or "27 Sep to 3 Oct".
    static func weekRange(_ start: String, _ end: String) -> String {
        let sameMonth = start.prefix(7) == end.prefix(7)
        let startText = sameMonth
            ? (FinanceMapping.date(start).map { FinanceMapping.format($0, template: "d") } ?? start)
            : ForecastText.shortDate(start)
        return L10n.tr("\(startText) to \(ForecastText.shortDate(end))")
    }
}
