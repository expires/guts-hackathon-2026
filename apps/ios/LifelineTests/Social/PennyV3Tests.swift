import Foundation
import Testing
@testable import Lifeline

/// Penny V3 chat fixes (PENNY_V3_BUILD C5 and D1 to D6). W7.
@MainActor
@Suite("Penny V3 chat")
struct PennyV3Tests {
    /// Row ids and mode labels on screen at each typing pause, while the answer streams.
    final class Recorder: @unchecked Sendable {
        var rowIDs: [[String]] = []
        var modeLabels: [[String]] = []
        weak var model: PennyViewModel?
    }

    static func answers(_ state: PennyViewState) -> [PennyViewState.AnswerGroup] {
        PennyViewModelTests.groups(state)
    }

    /// The labels the view shows: one per complete answer, none while streaming.
    static func shownLabels(_ state: PennyViewState) -> [String] {
        answers(state).filter(\.isComplete).map(\.modeLabel)
    }

    func streamedModel(_ recorder: Recorder, context: PennyContext = PennyContext(screen: .money)) -> PennyViewModel {
        let service = PennyFixtures.scripted(
            events: PennyFixtures.answerEvents,
            sleep: { [recorder] _ in
                await MainActor.run {
                    guard let state = recorder.model?.state else { return }
                    recorder.rowIDs.append(state.rows.map(\.id))
                    recorder.modeLabels.append(PennyV3Tests.shownLabels(state))
                }
            },
            now: PennyFixtures.now
        )
        let model = PennyViewModel(service: service, context: context)
        recorder.model = model
        return model
    }

    // MARK: D1 double bubble

    @Test func streamThenDoneShowsOneSetOfBubbles() async throws {
        let recorder = Recorder()
        let model = streamedModel(recorder)
        model.send("What if I lose my job?")
        await model.waitForTurn()

        let state = model.state
        let groups = Self.answers(state)
        // One question and one answer: the final answer replaced the streamed one.
        #expect(state.rows.count == 2)
        #expect(groups.count == 1)
        let expected = PennyFixtures.answerResponse.bubbles.prefix(PennyMapping.maxBubbles).map(\.id)
        #expect(groups[0].bubbles.map(\.id) == Array(expected))
        #expect(Set(groups[0].bubbles.map(\.id)).count == groups[0].bubbles.count)
        // The answer row keeps the id it had while streaming, so the view replaces it in place.
        let streamingAnswerIDs = recorder.rowIDs.flatMap { $0 }.filter { $0.hasPrefix("a.") }
        #expect(!streamingAnswerIDs.isEmpty)
        #expect(Set(streamingAnswerIDs) == [state.rows[1].id])
        // The question row keeps its id when the server id replaces the local id.
        #expect(state.rows[0].id == "q.local-1")
        if case let .question(question) = state.rows[0] { #expect(question.id == "msg_1") }
        // Never more than one answer row on screen during the stream.
        let rowsWhileStreaming = recorder.rowIDs
        #expect(rowsWhileStreaming.allSatisfy { ids in ids.filter { $0.hasPrefix("a.") }.count <= 1 })
        // One mode label per answer: none while streaming, one when done.
        let labelsWhileStreaming = recorder.modeLabels
        #expect(labelsWhileStreaming.allSatisfy { $0.isEmpty })
        #expect(Self.shownLabels(state).count == 1)
    }

    @Test func retryUsesTheStableRowID() async throws {
        let model = PennyViewModel(service: PennyFixtures.scripted(events: [], streamError: URLError(.timedOut), now: PennyFixtures.now))
        model.send("Hi")
        await model.waitForTurn()
        guard case let .failed(id, _)? = model.state.rows.last else { Issue.record("no failed row"); return }
        #expect(id == "local-1")
        model.retry(exchangeKey: id)
        #expect(model.isWorking)
        await model.waitForTurn()
    }

    // MARK: D6 max 3 bubbles

    @Test func atMostThreeBubblesPerAnswer() {
        var response = PennyFixtures.generalResponse
        let template = response.bubbles[0]
        response.bubbles = (1...5).map { index in
            var bubble = template
            bubble.id = "g\(index)"
            bubble.text = "Bubble \(index)."
            return bubble
        }
        let group = PennyMapping.answerGroup(response, presentation: false, now: PennyFixtures.now)
        #expect(group.bubbles.map(\.id) == ["g1", "g2", "g3"])
    }

    // MARK: C5 Try Penny

    @Test func tryPennyOpensWithTheNewGreetingAndNoRepliesLabel() async {
        let model = PennyViewModel(
            service: PennyFixtures.scripted(events: PennyFixtures.answerEvents, now: PennyFixtures.now),
            context: PennyContext(screen: .onboarding)
        )
        await model.start()
        let intro = model.state.introText
        #expect(intro.hasPrefix("Hi, I'm Penny, your student money guide."))
        #expect(intro.contains("Once you pick a student, I'll use their numbers too, and check every one."))
        #expect(!intro.contains("can't see"))
        #expect(!model.state.showsPastChats)
        #expect(!model.state.showsNewChat)
        model.send("How does the maintenance loan work?")
        await model.waitForTurn()
        let questions = model.state.rows.compactMap { if case let .question(q) = $0 { q } else { nil } }
        #expect(questions.count == 1)
        #expect(questions.allSatisfy { $0.replyCount == 0 })
        // Still no header buttons in onboarding.
        #expect(!model.state.showsNewChat)
    }

    @Test func greetingIsTranslatedInEveryLanguage() {
        let english = PennyViewModel.onboardingIntroText
        for language in AppLanguage.allCases where language != .en {
            let text = L10n.tr("Hi, I'm Penny, your student money guide. Ask me anything about money or uni life: budgets, loans, rent, part-time work, or anything in between. Once you pick a student, I'll use their numbers too, and check every one.", language: language)
            #expect(text != english, "Missing \(language) translation")
        }
    }

    // MARK: D2 New chat

    @Test func newChatClearsTheChatAndDoesNotResendTheQuestion() async {
        let tab = PennyTabModel(service: PennyFixtures.scripted(events: PennyFixtures.answerEvents, now: PennyFixtures.now))
        #expect(!tab.chat.state.showsNewChat)
        #expect(tab.chat.state.showsPastChats)
        tab.ask(PennyContext(screen: .nextMove, nextMoveID: "mv_1", question: "Why this move?"))
        await tab.chat.waitForTurn()
        #expect(tab.chat.state.showsNewChat)
        tab.chat.actions.onNewChat()
        #expect(tab.chat.exchanges.isEmpty)
        #expect(tab.chat.threadID == nil)
        #expect(tab.chat.context.question == nil)
        #expect(!tab.chat.isWorking)
        #expect(tab.chat.state.chips == PennyViewModel.chips)
        #expect(!tab.chat.state.showsNewChat)
    }

    // MARK: D3 Past chats

    static let threadsJSON = """
    {"threads":[
      {"id":"th_1","title":"Prices creep up","updated_at":"2026-10-17T12:00:00Z","message_count":2},
      {"id":"th_2","title":"Prices creep up","updated_at":"2026-10-16T12:00:00Z","message_count":2},
      {"id":"th_3","title":"How do I make a weekly budget?","updated_at":"2026-10-17T13:00:00Z","message_count":4}
    ]}
    """

    @Test func pastChatsRemoveDuplicateThreads() throws {
        let response = try JSONDecoder().decode(PennyAPI.ThreadsResponse.self, from: Data(Self.threadsJSON.utf8))
        let rows = PennyMapping.pastThreads(response)
        // Newest first; the older "Prices creep up" shows once.
        #expect(rows.map(\.id) == ["th_3", "th_1"])
    }

    @Test func pastChatsOpenOnTheirOwnScreen() async throws {
        let threads = try JSONDecoder().decode(PennyAPI.ThreadsResponse.self, from: Data(Self.threadsJSON.utf8))
        var service = PennyFixtures.scripted(events: [], threads: threads, now: PennyFixtures.now)
        let stored = PennyFixtures.decode(PennyAPI.Thread.self, """
        {"id":"th_1","title":"Prices creep up","messages":[
          {"id":"msg_1","role":"user","created_at":"2026-10-17T12:00:00Z","text":"Prices creep up","replies":1},
          {"id":"msg_2","role":"penny","created_at":"2026-10-17T12:00:00Z","reply_to":"msg_1","response":\(PennyFixtures.answerJSON)}
        ]}
        """)
        service.getThread = { _ in stored }
        let model = PennyViewModel(service: service)
        await model.start()
        // The empty chat no longer lists earlier chats inline; the header button opens them.
        #expect(model.state.showsPastChats)
        #expect(!model.state.isPastChatsOpen)
        model.actions.onOpenPastChats()
        #expect(model.state.isPastChatsOpen)
        #expect(model.state.pastThreads.map(\.id) == ["th_3", "th_1"])
        model.actions.onOpenPastThread("th_1")
        #expect(!model.state.isPastChatsOpen)
        await model.waitForTurn()
        #expect(model.threadID == "th_1")
        #expect(model.state.rows.count == 2)
        model.actions.onOpenPastChats()
        model.actions.onClosePastChats()
        #expect(!model.state.isPastChatsOpen)
    }

    // MARK: D4 context

    @Test func forecastContextAsksAboutTheWeeklyBudget() {
        let context = PennyContext.forecast
        #expect(context.question == "Explain my weekly budget")
        let chat = PennyMapping.chatContext(context, isNewThread: true)
        #expect(chat.screen?.rawValue == "forecast")
        #expect(chat.title == "Your weekly budget")
    }

    @Test func learnCardContextNamesTheCard() {
        let context = PennyContext.learnCard(
            lessonID: "budget_1", lessonTitle: "Make a budget", cardTitle: "Needs and wants",
            cardText: "Needs are rent and food. Wants are nights out."
        )
        #expect(context.question?.hasPrefix("Explain this card simply: Needs and wants") == true)
        #expect(context.question?.contains("Needs are rent and food.") == true)
        let chat = PennyMapping.chatContext(context, isNewThread: true)
        #expect(chat.screen?.rawValue == "learn_lesson")
        #expect(chat.lessonId == "budget_1")
        #expect(chat.title == "Make a budget")
    }

    // MARK: Data chips

    static let sample = PennyChipData(
        perWeek: 82,
        biggestCategory: "Eating out",
        nextMoneyLabel: "Student Finance England loan",
        nextMoneyDate: PennyChips.day("2026-10-28"),
        today: PennyChips.day("2026-10-18") ?? Date()
    )

    @Test func chipsUseTheStudentsNumbers() {
        let chips = PennyChips.chips(Self.sample)
        #expect(chips.count == 4)
        // About 10% of £82 a week, to the nearest £5.
        #expect(chips[0] == "Can I afford £10 on eating out this week?")
        #expect(chips[1] == "What if my Student Finance England loan is a week late?")
        #expect(chips[2] == "What if I spend £20 less on eating out a week?")
        // The first Friday after 18 Oct 2026 (a Sunday), before the loan on 28 Oct.
        #expect(chips[3].hasPrefix("Can I afford a £60 night out on "))
        #expect(chips[3].contains("23"))
    }

    @Test func chipsFromTheForecastPutWhatIfFirst() {
        let chips = PennyChips.chips(Self.sample, whatIfFirst: true)
        #expect(chips.first == "What if my Student Finance England loan is a week late?")
        #expect(chips[1].hasPrefix("What if I spend"))
    }

    @Test func chipsSkipWhatIsMissing() {
        var data = Self.sample
        data.nextMoneyLabel = nil
        data.nextMoneyDate = nil
        let chips = PennyChips.chips(data)
        #expect(chips.count == 2)
        #expect(!chips.contains { $0.contains("late") || $0.contains("night out") })
        #expect(PennyChips.lowerFirst("Pay from the bar job") == "pay from the bar job")
    }

    @Test func chipDataComesFromForecastAndSpending() async throws {
        let client = MockClient(data: .recorded)
        let forecast = try await client.forecast(bufferPct: nil, stress: nil)
        let spending = try await client.financeSpending(month: nil)
        let data = PennyChips.data(forecast: forecast, spending: spending)
        let biggest = spending.categories
            .filter { !PennyChips.skippedCategories.contains($0.category.rawValue) && $0.amount > 0 }
            .max { $0.amount < $1.amount }
        #expect(data.biggestCategory == biggest?.label)
        let next: Components.Schemas.NextMoney? = forecast.nextMoney
        if forecast.state.rawValue != "no_next_money", let next {
            #expect(data.nextMoneyLabel == next.label)
            #expect(data.nextMoneyDate == PennyChips.day(next.date))
        }
    }

    @Test func chatShowsDataChipsAndFallsBackWithout() async {
        var service = PennyFixtures.scripted(events: [], now: PennyFixtures.now)
        let sample = Self.sample
        service.loadChipData = { onUpdate in await onUpdate(sample) }
        let model = PennyViewModel(service: service, context: PennyContext(screen: .money))
        await model.start()
        await waitUntil { model.chipData != nil }
        #expect(model.state.chips == PennyChips.chips(Self.sample))

        let forecastChat = PennyViewModel(service: service, context: PennyContext(screen: .forecast, title: "What if..."))
        await forecastChat.start()
        await waitUntil { forecastChat.chipData != nil }
        #expect(forecastChat.state.chips.first == "What if my Student Finance England loan is a week late?")

        let noData = PennyViewModel(service: PennyFixtures.scripted(events: [], now: PennyFixtures.now))
        await noData.start()
        #expect(noData.state.chips == PennyViewModel.chips)

        let onboarding = PennyViewModel(service: service, context: PennyContext(screen: .onboarding))
        await onboarding.start()
        #expect(onboarding.state.chips == PennyViewModel.onboardingChips)
        #expect(!onboarding.state.showsHeader)
    }

    func waitUntil(_ condition: () -> Bool) async {
        for _ in 0..<400 where !condition() {
            try? await Task.sleep(for: .milliseconds(5))
        }
    }

    @Test func learnCardSendsTheCardIndex() {
        let context = PennyContext.learnCard(lessonID: "l1", lessonTitle: "Budgets", cardIndex: 2, cardTitle: "Wants", cardText: "")
        #expect(PennyMapping.chatContext(context, isNewThread: true).cardIndex == 2)
    }

    // MARK: D5 links

    @Test func linksOpenTheRightScreen() {
        #expect(PennyLink.why.destination == .theMaths)
        #expect(PennyLink.why.title == "See the maths")
        #expect(PennyLink.nextMove.destination == .moneyForecast)
        #expect(PennyLink.plan.destination == .moneyForecast)
        #expect(PennyLink.testIt.destination == .moneyForecast)
        #expect(PennyLink.maths.destination == .theMaths)
        #expect(PennyLink.forecast.destination == .moneyForecast)
        #expect(PennyLink(rawValue: "maths") == .maths)
    }
}
