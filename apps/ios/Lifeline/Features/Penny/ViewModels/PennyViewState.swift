import Foundation

/// Where the chat was opened from. Sent as `ChatRequest.context` so Penny does not ask again.
struct PennyContext: Hashable, Sendable, Identifiable {
    enum Screen: String, Hashable, Sendable {
        case money, nextMove = "next_move", why, lifeEvent = "life_event", life, other
    }

    var screen: Screen = .other
    var nextMoveID: String?
    var lifeID: String?
    var eventID: String?
    /// Sent once when the chat opens, for example "Why this move?". Nil opens an empty chat.
    var question: String?

    var id: String {
        [screen.rawValue, nextMoveID, lifeID, eventID, question].map { $0 ?? "-" }.joined(separator: "|")
    }

    init(screen: Screen = .other, nextMoveID: String? = nil, lifeID: String? = nil, eventID: String? = nil, question: String? = nil) {
        self.screen = screen
        self.nextMoveID = nextMoveID
        self.lifeID = lifeID
        self.eventID = eventID
        self.question = question
    }
}

/// In-app destinations from `ChatResponse.links`. The caller decides how to open them.
enum PennyLink: String, Equatable, Sendable, CaseIterable {
    case nextMove = "next_move", testIt = "test_it", why, plan

    /// Button text.
    var title: String {
        switch self {
        case .nextMove: "See the Next Move"
        case .testIt: "Test it"
        case .why: "Why this move?"
        case .plan: "Open your plan"
        }
    }
}

/// Penny's tapback on the user's question. Set within 1 s, before the answer (ADR 0031).
enum PennyReaction: String, Equatable, Sendable, CaseIterable {
    case eyes, brain, thumbs, tick, question, shrug

    /// VoiceOver text.
    var label: String {
        switch self {
        case .eyes: "Penny is looking at your data"
        case .brain: "Penny is working it out"
        case .thumbs: "Penny agrees"
        case .tick: "Done"
        case .question: "Penny is not sure"
        case .shrug: "Penny cannot help with this"
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
            case let .question(q): "q." + q.id
            case let .answer(a): "a." + a.id
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
    /// Earlier chats (`GET /v1/chat/threads`), shown on an empty chat.
    var pastThreads: [ThreadSummary]
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
    var onRetry: @MainActor (String) -> Void = { _ in }
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
