import Foundation

/// Where the chat was opened from. Sent as `ChatRequest.context` so Penny does not ask again.
struct PennyContext: Hashable, Sendable, Identifiable {
    enum Screen: String, Hashable, Sendable {
        case money, nextMove = "next_move", why, lifeEvent = "life_event", life, other
        /// Onboarding (ADR 0063): no finance data yet. General answers, student starter chips, no Next Move links.
        case onboarding
        /// "What does this result mean?" on Test it.
        case testIt = "test_it"
        /// A multiplayer room round (Same Decision, or an event in a Same Life room).
        case roomRound = "room_round"
        /// A Learn lesson (ADR 0068). The server loads the lesson's cards and facts.
        case learnLesson = "learn_lesson"
        /// The Money forecast ("Explain my weekly budget", PENNY_V3_BUILD D4). The server loads the forecast.
        case forecast
    }

    var screen: Screen = .other
    var nextMoveID: String?
    var lifeID: String?
    var eventID: String?
    /// Sent once when the chat opens, for example "Why this move?". A question starts a NEW chat.
    /// Nil opens the chat without sending anything.
    var question: String?
    /// Thread title from the context, for example "Safety fund, age 19". Nil uses `threadTitle`'s default.
    var title: String?
    /// A multiplayer round: Penny explains the trade-offs and does not pick for the player.
    var isMultiplayer = false
    /// Room code and Same Decision prompt id (screen `roomRound`). The server loads the round's options.
    var roomCode: String?
    var roundID: String?
    /// Learn lesson id (screen `learnLesson`).
    var lessonID: String?
    /// The lesson card on screen, from 0 (D4). Sent as `card_index`.
    var cardIndex: Int?

    var id: String {
        [screen.rawValue, nextMoveID, lifeID, eventID, question, title, roomCode, roundID, lessonID, cardIndex.map(String.init)].map { $0 ?? "-" }.joined(separator: "|")
    }

    init(
        screen: Screen = .other,
        nextMoveID: String? = nil,
        lifeID: String? = nil,
        eventID: String? = nil,
        question: String? = nil,
        title: String? = nil,
        isMultiplayer: Bool = false,
        roomCode: String? = nil,
        roundID: String? = nil,
        lessonID: String? = nil
    ) {
        self.screen = screen
        self.nextMoveID = nextMoveID
        self.lifeID = lifeID
        self.eventID = eventID
        self.question = question
        self.title = title
        self.isMultiplayer = isMultiplayer
        self.roomCode = roomCode
        self.roundID = roundID
        self.lessonID = lessonID
    }

    /// `ChatContext.title`: the server titles the NEW thread with it. Nil for a chat with no context
    /// (the server titles it from the first message).
    var threadTitle: String? {
        if let title = title?.trimmingCharacters(in: .whitespacesAndNewlines), !title.isEmpty {
            return String(title.prefix(80))
        }
        return switch screen {
        case .nextMove: L10n.tr("Your Next Move")
        case .why: L10n.tr("Next Move, explained")
        case .testIt: L10n.tr("Test it result")
        case .lifeEvent: L10n.tr("Life event")
        case .roomRound: L10n.tr("Room round")
        case .forecast: L10n.tr("Your weekly budget")
        case .money, .life, .other, .onboarding, .learnLesson: nil
        }
    }

    /// "Safety fund, age 19". The thread title for a life event or a room round.
    static func eventTitle(_ eventTitle: String, age: Int?) -> String {
        let name = eventTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let age else { return name }
        return L10n.tr("\(name), age \(age)")
    }
}

extension PennyContext {
    /// "Not sure? Ask Penny" on a life event. The server plays each option forward with the engine
    /// (`event_choices`), so every number is a game number. In a Same Life room (`roomCode` set)
    /// Penny explains only and does not pick.
    static func lifeEvent(lifeID: String?, eventID: String?, eventTitle: String, age: Int?, roomCode: String? = nil) -> PennyContext {
        let multiplayer = roomCode != nil
        return PennyContext(
            screen: .lifeEvent, lifeID: lifeID, eventID: eventID,
            question: multiplayer ? PennyQuestion.roomRound : PennyQuestion.lifeEvent,
            title: eventTitle.isEmpty ? nil : PennyContext.eventTitle(eventTitle, age: age),
            isMultiplayer: multiplayer, roomCode: roomCode
        )
    }

    /// "Not sure? Ask Penny" in a Same Decision round. The server loads the round's options;
    /// game money outcomes stay hidden until the reveal.
    static func roomRound(roomCode: String, roundID: String?, year: Int?) -> PennyContext {
        PennyContext(
            screen: .roomRound,
            question: PennyQuestion.roomRound,
            title: year.map { L10n.tr("Same Decision, \(String($0))") } ?? L10n.tr("Same Decision"),
            isMultiplayer: true, roomCode: roomCode, roundID: roundID
        )
    }
}

/// The questions each "Ask Penny" entry point sends at once (DIRECTION_V2, Ask Penny context fix).
enum PennyQuestion {
    /// Life event (solo): Penny explains the trade-offs with game numbers.
    static var lifeEvent: String { L10n.tr("Which option should I pick?") }
    /// Multiplayer round: Penny explains only, so the question does not ask her to pick.
    static var roomRound: String { L10n.tr("What are the trade-offs here?") }
    static var nextMove: String { L10n.tr("Why this move?") }
    static var why: String { L10n.tr("Explain this simply") }
    static var testIt: String { L10n.tr("What does this result mean?") }
    /// "Ask Penny" on the Money forecast (D4).
    static var forecast: String { L10n.tr("Explain my weekly budget") }
    /// "Ask Penny" on a Learn card (D4): about the card on screen, not the whole lesson.
    static func learnCard(title: String) -> String { L10n.tr("Explain this card simply: \(title)") }
}

extension PennyContext {
    /// "Ask Penny" on the Money forecast: a new chat that sends "Explain my weekly budget" with the forecast loaded.
    static var forecast: PennyContext {
        PennyContext(screen: .forecast, question: PennyQuestion.forecast)
    }

    /// "Ask Penny" on a Learn card (D4). The question names the card and carries its text, so Penny explains
    /// that card. `lesson_id` lets the server load the lesson's facts. Card text over 400 characters is cut.
    static func learnCard(lessonID: String, lessonTitle: String, cardIndex: Int? = nil, cardTitle: String, cardText: String) -> PennyContext {
        let title = cardTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        var text = cardText.trimmingCharacters(in: .whitespacesAndNewlines)
        if text.count > 400 { text = String(text.prefix(400)) + "…" }
        let head = PennyQuestion.learnCard(title: title.isEmpty ? lessonTitle : title)
        var context = PennyContext(
            screen: .learnLesson,
            question: text.isEmpty ? head : head + "\n\n\"" + text + "\"",
            title: lessonTitle.isEmpty ? nil : lessonTitle,
            lessonID: lessonID
        )
        context.cardIndex = cardIndex
        return context
    }
}

/// In-app destinations from `ChatResponse.links`. The caller decides how to open them.
enum PennyLink: String, Equatable, Sendable, CaseIterable {
    case nextMove = "next_move", testIt = "test_it", why, plan, maths, forecast

    /// Button text.
    var title: String {
        switch self {
        case .nextMove: L10n.tr("See the Next Move")
        case .testIt: L10n.tr("Test it")
        case .why: L10n.tr("See the maths")
        case .plan: L10n.tr("Open your plan")
        case .maths: L10n.tr("See the maths")
        case .forecast: L10n.tr("See your weekly budget")
        }
    }

    /// The screen the link opens (PENNY_V3_BUILD D5). The app routes each destination.
    var destination: PennyDestination {
        switch self {
        case .why, .maths: .theMaths
        case .nextMove, .testIt, .plan, .forecast: .moneyForecast
        }
    }
}

/// Where a Penny link button goes (D5). Test it and the plan were cut in V3 (B4), so they open the forecast.
enum PennyDestination: Equatable, Sendable {
    /// Money tab, scrolled to the top: the forecast card ("Your Next Move").
    case moneyForecast
    /// Money tab, then push "The maths" (the forecast steps and their sources).
    case theMaths
}

/// Penny's tapback on the user's question. Set within 1 s, before the answer (ADR 0031).
enum PennyReaction: String, Equatable, Sendable, CaseIterable {
    case eyes, brain, thumbs, tick, question, shrug

    /// VoiceOver text.
    var label: String {
        switch self {
        case .eyes: L10n.tr("Penny is looking at your data")
        case .brain: L10n.tr("Penny is working it out")
        case .thumbs: L10n.tr("Penny agrees")
        case .tick: L10n.tr("Done")
        case .question: L10n.tr("Penny is not sure")
        case .shrug: L10n.tr("Penny cannot help with this")
        }
    }
}

/// Ask Penny (ADR 0031 and its perceived-speed amendment). Plain values only (ADR 0011).
struct PennyViewState: Equatable, Sendable {
    /// One part of a bubble's text. Highlighted parts are numbers the user can tap.
    struct Segment: Equatable, Sendable, Identifiable {
        var id: Int
        var text: String
        /// Set on a highlighted number.
        var highlightID: String?
    }

    /// One Penny bubble. Every bubble on screen passed the verifier (`bubble` event or `done`).
    struct Bubble: Equatable, Sendable, Identifiable {
        enum Kind: String, Equatable, Sendable { case answer, caveat, question, generalKnowledge }
        var id: String
        var kind: Kind
        var segments: [Segment]
        /// The full text, for VoiceOver.
        var text: String
    }

    /// The small card that opens when the user taps a highlighted number.
    struct HighlightDetail: Equatable, Sendable, Identifiable {
        /// "<groupID>.<bubbleID>.<index>".
        var id: String
        var bubbleID: String
        /// "Months of cover".
        var label: String
        /// "4 months". Money is rounded in presentation mode.
        var valueText: String
        /// "Your accounts".
        var sourceLabel: String?
        /// "Updated 5 min ago".
        var updatedText: String?
        var status: DataStatus?
    }

    struct SourceRow: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var updatedText: String?
        var status: DataStatus?
        var url: URL?
    }

    struct SourceGroup: Equatable, Sendable, Identifiable {
        /// "your_data", "live_sources", "general_knowledge".
        var id: String
        /// "Your data", "Live sources", "General knowledge".
        var title: String
        var rows: [SourceRow]
    }

    /// Penny's reply to one question: verified bubbles, then links, then the sources card.
    struct AnswerGroup: Equatable, Sendable, Identifiable {
        var id: String
        /// Stable row identity for one answer (D1). The streamed group and the final group of the same answer
        /// share it, so the final bubbles replace the streamed ones in place. Empty uses `id`.
        var rowKey: String = ""
        var bubbles: [Bubble]
        var highlights: [String: HighlightDetail]
        /// 0 to 1. Penny's face follows it.
        var confidence: Double
        var links: [PennyLink]
        var sourceGroups: [SourceGroup]
        /// "See sources (3)".
        var sourcesTitle: String
        /// "Penny is AI and can make mistakes. …" Shown only in the sources card footer (ADR 0051).
        var disclaimer: String
        /// "Checked with your data" (engine tool used) or "General answer" (ADR 0051).
        var modeLabel: String = PennyMapping.checkedLabel
        var isChecked: Bool = true
        /// Follow-up chips from `ChatResponse.suggestions` (max 2). Shown under the newest answer only.
        var suggestions: [String] = []
        /// False: the plain template summary (the verifier failed). The view shows a note.
        var isVerified: Bool
        /// True while bubbles still arrive.
        var isComplete: Bool
    }

    /// One user message. Penny's answer groups attach to it.
    struct Question: Equatable, Sendable, Identifiable {
        var id: String
        /// Stable row identity (D1): it does not change when the server's message id replaces the local id.
        var rowKey: String = ""
        var text: String
        var reaction: PennyReaction?
        /// "N Replies" under the bubble. 0 hides the link.
        var replyCount: Int
        /// Follow-up questions asked inside this question's thread.
        var isReply: Bool
    }

    /// One row of the timeline.
    enum Row: Equatable, Sendable, Identifiable {
        case question(Question)
        case answer(AnswerGroup)
        /// Typing dots under Penny, with the current real tool step ("Checking Bank of England…").
        case working(id: String, step: String?)
        case failed(id: String, error: ErrorViewState)

        var id: String {
            switch self {
            case let .question(q): "q." + (q.rowKey.isEmpty ? q.id : q.rowKey)
            case let .answer(a): "a." + (a.rowKey.isEmpty ? a.id : a.rowKey)
            case let .working(id, _): "w." + id
            case let .failed(id, _): "f." + id
            }
        }
    }

    struct ThreadSummary: Equatable, Sendable, Identifiable {
        var id: String
        var title: String
        /// "2 messages · 17 Oct".
        var detail: String
    }

    var title: String
    /// Nil on the main chat. Set when the user opened "N Replies".
    var openThreadQuestionID: String?
    var rows: [Row]
    /// Starter questions. Only on an empty chat, inside the chat area (never over messages).
    var chips: [String]
    /// False in the Penny tab (no close button).
    var showsClose = true
    /// The one Penny row that shows her face: the newest Penny row (answer, typing or failed).
    var pennyFaceRowID: String? = nil
    /// Answer group id whose `suggestions` show as chips (the newest finished answer).
    var suggestionsGroupID: String? = nil
    /// Past chats (`GET /v1/chat/threads`), newest first, no duplicates. Shown on the Past chats screen (D3).
    var pastThreads: [ThreadSummary]
    /// False in onboarding: the Try Penny step has its own header (Back, Skip), so the chat header would repeat it.
    var showsHeader = true
    /// "New chat" in the header (D2). Hidden on an empty chat and in onboarding.
    var showsNewChat = false
    /// "Past chats" in the header (D3). Hidden in onboarding.
    var showsPastChats = false
    /// The Past chats screen is open.
    var isPastChatsOpen = false
    var isWorking: Bool
    var canSend: Bool
    /// Penny's face: the last answer's confidence, or thinking while she works.
    var pennyMood: PennyMood
    /// Highlight ids of the open number card. One at a time.
    var openHighlightID: String?
    /// Answer group ids with an expanded sources card.
    var expandedSourceGroups: Set<String>
    /// Presentation mode: money amounts are rounded in every bubble and card (DesignSystem `LLAmountFormat`).
    var isPresentation: Bool
    var inputPlaceholder: String
    /// Intro bubble on an empty chat.
    var introText: String = PennyViewModel.introText

    var isEmpty: Bool { rows.isEmpty }
}

/// Penny's face. Mirrors `PennyView.Mood` so the state stays free of SwiftUI.
enum PennyMood: Equatable, Sendable {
    case happy, thinking, neutral, smiling

    /// Same thresholds as `PennyView.mood(confidence:)`.
    static func from(confidence: Double) -> PennyMood {
        confidence >= 0.75 ? .happy : (confidence >= 0.5 ? .thinking : .neutral)
    }
}

/// Closures for `PennyChatView`. The glue wires them.
struct PennyActions {
    var onSend: @MainActor (String) -> Void = { _ in }
    var onChip: @MainActor (String) -> Void = { _ in }
    /// "N Replies" under a question.
    var onOpenThread: @MainActor (String) -> Void = { _ in }
    /// Back from a thread to the main chat.
    var onCloseThread: @MainActor () -> Void = {}
    /// Tap on a highlighted number. The same id again closes the card.
    var onTapHighlight: @MainActor (String) -> Void = { _ in }
    var onToggleSources: @MainActor (String) -> Void = { _ in }
    var onLink: @MainActor (PennyLink) -> Void = { _ in }
    var onOpenPastThread: @MainActor (String) -> Void = { _ in }
    /// "New chat" in the header (D2).
    var onNewChat: @MainActor () -> Void = {}
    /// "Past chats" in the header (D3): opens the list.
    var onOpenPastChats: @MainActor () -> Void = {}
    /// Closes the Past chats screen without opening a chat.
    var onClosePastChats: @MainActor () -> Void = {}
    var onRetry: @MainActor (String) -> Void = { _ in }
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
