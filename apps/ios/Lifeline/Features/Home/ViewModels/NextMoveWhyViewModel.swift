import Foundation
import Observation

/// "Why?" for one move. Evidence comes from the move. The lesson comes from `GET /v1/concepts`.
/// When the lesson has no `personal` sentence, the matching `PersonalFact` from
/// `GET /v1/finance/profile` fills it (same concept id; every number comes from its `facts`).
@MainActor
@Observable
final class NextMoveWhyViewModel {
    static var loadingMessage: String { L10n.tr("Loading the lesson") }

    private let client: any LifelineClient
    let move: Move
    private let isSampleData: Bool
    private(set) var lesson: Lesson?
    private(set) var lessonPhase: LoadPhase = .loading(.init(message: NextMoveWhyViewModel.loadingMessage))
    /// Set by "Open the lesson". The glue presents `LessonScreen` and clears it.
    var presentedLesson: Lesson?
    /// The profile character from `GET /v1/finance/profile`. The Decision screen needs it.
    private(set) var character: CharacterSpec?
    @ObservationIgnored var onOpenDecision: @MainActor () -> Void = {}
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(client: any LifelineClient, move: Move, isSampleData: Bool) {
        self.client = client
        self.move = move
        self.isSampleData = isSampleData
    }

    var state: NextMoveWhyViewState {
        var state = Self.makeState(move: move, lesson: lesson, lessonPhase: lessonPhase, isSampleData: isSampleData)
        state.hasDecisionDetail = character != nil && Self.hasDecisionDetail(move)
        return state
    }

    var actions: NextMoveWhyActions {
        NextMoveWhyActions(
            onOpenLesson: { [weak self] in
                guard let self, let lesson else { return }
                presentedLesson = lesson
            },
            onOpenDecision: { [weak self] in
                guard let self, character != nil, Self.hasDecisionDetail(move) else { return }
                onOpenDecision()
            },
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    /// "High", "Medium" or "Low": the same level as the card (the engine's confidence_level). Empty without a level.
    static func confidenceChip(_ move: Move) -> String {
        guard let level = move.confidenceLevel else { return "" }
        return switch level {
        case .high: L10n.tr("High")
        case .medium: L10n.tr("Medium")
        case .low: L10n.tr("Low")
        }
    }

    /// Mortgage moves have a full decision screen (`POST /v1/decisions`).
    static func hasDecisionDetail(_ move: Move) -> Bool {
        move.kind == .fixMortgage || move.kind == .remortgage
    }

    func load() async {
        let profile = try? await client.financeProfile()
        character = profile?.character
        guard let conceptID = move.conceptId else {
            lessonPhase = .ready
            return
        }
        lessonPhase = .loading(.init(message: Self.loadingMessage))
        do {
            let concepts = try await client.listConcepts()
            guard var found = concepts.first(where: { $0.id == conceptID })?.lesson else {
                lesson = nil
                lessonPhase = .ready
                return
            }
            if found.personal == nil, let profile {
                found.personal = profile.personalFacts.first(where: { $0.conceptId == conceptID })?.text
            }
            lesson = found
            lessonPhase = .ready
        } catch {
            lessonPhase = .failed(.from(APIError.map(error)))
        }
    }

    // MARK: Mapping (pure, used by fixtures and tests)

    static func makeState(move: Move, lesson: Lesson?, lessonPhase: LoadPhase, isSampleData: Bool) -> NextMoveWhyViewState {
        var state = NextMoveWhyViewState(
            action: move.action,
            headline: move.headline,
            confidenceLabel: move.confidenceLabel,
            evidence: move.evidence.enumerated().map { offset, point in
                .init(id: offset, text: point.text, source: point.source.map(StateMapping.sourceChip))
            },
            sources: move.sources.map(StateMapping.sourceChip),
            lessonPhase: lessonPhase,
            lesson: lesson.map { .init(title: $0.title, sentences: $0.sentences, personal: $0.personal) },
            isSampleData: isSampleData,
            confidence: move.confidence,
            // Same level as the card (the engine's confidence_level), so Why? and the card agree.
            confidenceChip: confidenceChip(move),
            worstCaseText: NextMoveViewModel.isYearly(move) ? NextMoveViewModel.worstCaseText(move.worstCasePerYear) : "",
            rates: rates(move),
            ratesSourceText: sourcesLine(move.sources + move.evidence.compactMap(\.source) + (move.tradeOff?.points.compactMap(\.source) ?? []))
        )
        state.confidenceText = NextMoveViewModel.confidenceText(move)
        state.sourceSentences = sourceSentences(move)
        state.tradeOffSummary = move.tradeOff?.summary
        state.tradeOff = (move.tradeOff?.points ?? []).enumerated().map { offset, point in
            .init(id: 100 + offset, text: point.text, source: point.source.map(StateMapping.sourceChip))
        }
        return state
    }

    /// Rate bars from evidence facts: `rate_<option id>` (for example `rate_5y`, `rate_tracker`) and `<option id>_pct`.
    /// `current_rate` is shown as the dashed reference bar ("Your rate now").
    static func rates(_ move: Move) -> [NextMoveWhyViewState.RateBar] {
        let recommended = move.options.first { $0.isRecommended == true }?.id
        var bars: [NextMoveWhyViewState.RateBar] = []
        func add(id: String, label: String, value: Double, optionID: String?, reference: Bool) {
            guard !bars.contains(where: { $0.id == id }) else { return }
            bars.append(.init(
                id: id, label: label, value: value,
                valueText: value.formatted(.number.precision(.fractionLength(2))) + "%",
                fraction: 0, isHighlighted: optionID != nil && optionID == recommended, isReference: reference
            ))
        }
        for point in move.evidence {
            guard let facts = point.facts?.additionalProperties else { continue }
            for option in move.options {
                let candidates = ["rate_" + option.id, "rate_" + option.id.replacingOccurrences(of: "fix_", with: ""), option.id + "_pct"]
                if let key = candidates.first(where: { facts[$0] != nil }), let value = facts[key] {
                    add(id: key, label: option.label, value: value, optionID: option.id, reference: false)
                }
            }
            if let current = facts["current_rate"] {
                add(id: "current_rate", label: L10n.tr("Your rate now"), value: current, optionID: nil, reference: true)
            }
            for key in facts.keys.sorted() where key.hasPrefix("bank_rate") {
                if let value = facts[key] { add(id: key, label: L10n.tr("Bank Rate"), value: value, optionID: nil, reference: true) }
            }
        }
        let top = bars.map(\.value).max() ?? 1
        return bars.map { var bar = $0; bar.fraction = top > 0 ? bar.value / top : 0; return bar }
    }

    static var combiningSentence: String { L10n.tr("Together: the move weighs all of these at once, which is better than any one source alone.") }

    /// One sentence per key source (the first sentence of its first evidence point), at most 3,
    /// then the combining sentence. Empty when no evidence point names a source.
    static func sourceSentences(_ move: Move) -> [String] {
        var seen: [String] = []
        var lines: [String] = []
        for point in move.evidence {
            guard let ref = point.source else { continue }
            let name = StateMapping.sourceName(ref.source)
            guard !seen.contains(name), lines.count < 3 else { continue }
            seen.append(name)
            let sentence = firstSentence(point.text)
            lines.append(L10n.tr("\(name): \(sentence)"))
        }
        guard !lines.isEmpty else { return [] }
        return lines + [combiningSentence]
    }

    /// "Your 4.42% fixed rate finishes in 165 days." from a longer text. Keeps decimals like "4.42".
    static func firstSentence(_ text: String) -> String {
        if let range = text.range(of: ". ") {
            return String(text[..<range.lowerBound]) + "."
        }
        return text.hasSuffix(".") ? text : text + "."
    }

    /// One line for all sources, grouped by source with the worst status: "Bank of England · live".
    static func sourcesLine(_ refs: [SourceRef]) -> String? {
        var order: [String] = []
        var worst: [String: DataStatus] = [:]
        let rank: [DataStatus: Int] = [.live: 0, .cached: 1, .mock: 2, .unavailable: 3]
        var isSample: Set<String> = []
        for ref in refs {
            let name = StateMapping.sourceName(ref.source)
            if ref.source.contains("sample") || ref.note == "Sample data" { isSample.insert(name) }
            let status = StateMapping.status(ref.status.rawValue)
            if worst[name] == nil { order.append(name) }
            if (rank[status] ?? 0) >= (rank[worst[name] ?? .live] ?? 0) { worst[name] = status }
        }
        guard !order.isEmpty else { return nil }
        // Human labels: "Your statement · sample data", "gov.uk · saved copy", "Bank of England · live".
        return order.map { name in
            let status = worst[name] ?? .mock
            let label = isSample.contains(name) && status == .mock ? "sample data" : status.label
            return "\(name) · \(label)"
        }.joined(separator: ", ")
    }

    /// "fix_5y" -> "5-year fix", "fix_2y" -> "2-year fix", "bank_rate" -> "Bank Rate".
    static func rateLabel(_ id: String) -> String {
        if id.hasPrefix("bank_rate") { return L10n.tr("Bank Rate") }
        if id.hasPrefix("fix_"), let years = Int(id.dropFirst(4).dropLast()) { return "\(years)-year fix" }
        return id.replacingOccurrences(of: "_", with: " ").capitalized
    }
}
