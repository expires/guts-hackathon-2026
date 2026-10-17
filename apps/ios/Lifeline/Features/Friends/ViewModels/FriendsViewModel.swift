import Foundation
import Observation

/// Loads the leaderboard and handles joining, removing and what friends see (`/v1/friends/*`).
@MainActor
@Observable
final class FriendsViewModel {
    static let loadingMessage = "Loading your friends"
    static let codeLength = AddFriendState.codeLength
    /// The invite code alphabet: no 0, O, 1, I or L, so codes are easy to read out.
    static let codeAlphabet = Set("ABCDEFGHJKMNPQRSTUVWXYZ23456789")
    static let nameLimit = 30

    private let client: any LifelineClient
    private(set) var board: Leaderboard?
    private(set) var myCard: FriendCard?
    private(set) var phase: LoadPhase = .loading(.init(message: FriendsViewModel.loadingMessage))
    private(set) var banner: FriendsViewState.Banner?
    private(set) var codeInput = ""
    private(set) var joinError: String?
    private(set) var isJoining = false
    private(set) var isRotating = false
    private(set) var nameDraft = ""
    private(set) var isSaving = false
    private(set) var cardError: String?
    private var inviteCode = ""

    init(client: any LifelineClient) {
        self.client = client
    }

    var state: FriendsViewState {
        Self.makeState(
            board: board, myCard: myCard, phase: phase, banner: banner, inviteCode: board?.myInviteCode ?? inviteCode,
            codeInput: codeInput, joinError: joinError, isJoining: isJoining, isRotating: isRotating,
            nameDraft: nameDraft, isSaving: isSaving, cardError: cardError
        )
    }

    var actions: FriendsActions {
        FriendsActions(
            onRetry: { [weak self] in Task { await self?.load() } },
            onRemove: { [weak self] id in Task { await self?.remove(id: id) } },
            onDismissBanner: { [weak self] in self?.banner = nil },
            onCodeChange: { [weak self] in self?.setCode($0) },
            onJoin: { [weak self] in Task { await self?.join() } },
            onRotate: { [weak self] in Task { await self?.rotateCode() } },
            onCopied: { [weak self] in self?.banner = .init(kind: .success, text: "Code copied") },
            onNameChange: { [weak self] in self?.nameDraft = String($0.prefix(Self.nameLimit)) },
            onSaveName: { [weak self] in Task { await self?.saveName() } },
            onShareMix: { [weak self] on in Task { await self?.setShareMix(on) } }
        )
    }

    // MARK: Loading

    func load() async {
        if board == nil { phase = .loading(.init(message: Self.loadingMessage)) }
        do {
            async let boardCall = client.leaderboard()
            async let cardCall = client.myFriendCard()
            let (loaded, card) = try await (boardCall, cardCall)
            board = loaded
            apply(card: card)
            phase = .ready
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    // MARK: Adding friends

    func setCode(_ raw: String) {
        codeInput = Self.clean(code: raw)
        joinError = nil
    }

    /// Joins with what is typed in the code field.
    func join() async {
        guard codeInput.count == Self.codeLength, !isJoining else { return }
        isJoining = true
        joinError = nil
        defer { isJoining = false }
        do {
            let updated = try await client.joinFriend(code: codeInput)
            board = updated
            phase = .ready
            codeInput = ""
            banner = .init(kind: .success, text: "Friend added")
        } catch {
            let text = Self.joinMessage(for: APIError.map(error))
            joinError = text
            banner = .init(kind: .failure, text: text)
        }
    }

    /// A `lifeline://join/CODE` link: fill the field and join at once.
    func handleDeepLink(code: String) async {
        setCode(code)
        guard codeInput.count == Self.codeLength else {
            let text = Self.joinMessage(for: .server(status: 404, code: "invite_not_found", message: "", source: "friends"))
            joinError = text
            banner = .init(kind: .failure, text: text)
            return
        }
        await join()
    }

    func rotateCode() async {
        guard !isRotating else { return }
        isRotating = true
        defer { isRotating = false }
        do {
            let invite = try await client.createFriendInvite(rotate: true)
            inviteCode = invite.code
            board?.myInviteCode = invite.code
            banner = .init(kind: .success, text: "You have a new code. The old one no longer works.")
        } catch {
            banner = .init(kind: .failure, text: APIError.map(error).userMessage)
        }
    }

    func remove(id: String) async {
        do {
            board = try await client.removeFriend(id: id)
            banner = .init(kind: .success, text: "Friend removed")
        } catch {
            banner = .init(kind: .failure, text: APIError.map(error).userMessage)
        }
    }

    // MARK: What friends see

    func saveName() async {
        let name = nameDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty, let card = myCard else { return }
        await save(name: name, shareMix: card.mix != nil)
    }

    func setShareMix(_ on: Bool) async {
        let name = (myCard?.displayName ?? nameDraft).trimmingCharacters(in: .whitespacesAndNewlines)
        await save(name: name.isEmpty ? "You" : name, shareMix: on)
    }

    private func save(name: String, shareMix: Bool) async {
        isSaving = true
        cardError = nil
        defer { isSaving = false }
        do {
            let card = try await client.updateMyFriendCard(ShareSettings(displayName: name, shareMix: shareMix))
            apply(card: card)
            board = try? await client.leaderboard()
            banner = .init(kind: .success, text: "Saved. Friends now see this.")
        } catch {
            cardError = APIError.map(error).userMessage
        }
    }

    private func apply(card: FriendCard) {
        myCard = card
        nameDraft = card.displayName
    }

    // MARK: Pure mapping (used by fixtures and tests)

    static func clean(code raw: String) -> String {
        String(raw.uppercased().filter { codeAlphabet.contains($0) }.prefix(codeLength))
    }

    static func joinMessage(for error: APIError) -> String {
        if case let .server(_, code, _, _) = error {
            switch code {
            case "invite_not_found": return "No one has that code. Check it and try again."
            case "cannot_add_self": return "That's your own code."
            default: break
            }
        }
        return error.userMessage
    }

    static let factorLabels: [String: String] = [
        "savings_rate": "Money you keep",
        "runway_months": "Cushion",
        "spend_stability": "Steady spending",
        "discretionary_share": "Treats",
        "subscription_creep": "Subscriptions",
        "isa_concentration": "Spread of your investments",
        "shock_resilience": "Bumps in the road",
    ]

    static let factorOrder = [
        "savings_rate", "runway_months", "spend_stability", "discretionary_share", "subscription_creep",
        "isa_concentration", "shock_resilience",
    ]

    static let mixLabels: [String: String] = [
        "equity": "Shares", "bond": "Bonds", "cash": "Cash", "commodity": "Commodities",
        "property": "Property", "other": "Other",
    ]

    static func band(_ score: Int) -> String { HabitsViewModel.band(score) }

    static func factorLabel(_ id: String) -> String {
        if let label = factorLabels[id] { return label }
        let words = id.replacingOccurrences(of: "_", with: " ")
        return words.prefix(1).uppercased() + words.dropFirst()
    }

    static func growthText(_ index: Double?) -> String? {
        index.map { "Investments: \(Int($0.rounded())), started at 100" }
    }

    static func compareText(theirs: Int?, mine: Int?) -> String? {
        guard let theirs, let mine else { return nil }
        let diff = theirs - mine
        let points = abs(diff) == 1 ? "1 point" : "\(abs(diff)) points"
        if diff > 0 { return "\(points) above you" }
        if diff < 0 { return "\(points) below you" }
        return "Same score as you"
    }

    static func detail(for card: FriendCard, isMe: Bool) -> FriendDetailState {
        let scores = card.factorScores.additionalProperties
        let ordered = factorOrder.filter { scores[$0] != nil } + scores.keys.filter { !factorOrder.contains($0) }.sorted()
        let factors = ordered.compactMap { id -> FriendDetailState.Factor? in
            guard let raw = scores[id] else { return nil }
            let score = min(100, max(0, raw))
            return .init(id: id, label: factorLabel(id), score: score, scoreText: "\(score) out of 100", bandText: band(score))
        }
        let slices = (card.mix?.additionalProperties ?? [:])
            .filter { $0.value > 0 }
            .sorted { $0.value > $1.value }
            .map { key, value in
                FriendDetailState.Slice(
                    id: key, label: mixLabels[key] ?? factorLabel(key), percent: value,
                    percentText: "\(Int(value.rounded())) percent"
                )
            }
        let owner = isMe ? "You have" : "\(card.displayName) has"
        return .init(
            id: card.friendId,
            name: card.displayName,
            isMe: isMe,
            score: card.overallScore,
            scoreText: card.overallScore.map(String.init) ?? "-",
            bandText: card.overallScore.map(band),
            growthText: growthText(card.growthIndex),
            factors: factors,
            slices: slices,
            mixNote: slices.isEmpty ? "\(owner) not shared \(isMe ? "your" : "their") investment mix." : nil,
            isSample: card.dataStatus == .mock
        )
    }

    static func makeState(
        board: Leaderboard?, myCard: FriendCard?, phase: LoadPhase, banner: FriendsViewState.Banner? = nil,
        inviteCode: String = "", codeInput: String = "", joinError: String? = nil, isJoining: Bool = false,
        isRotating: Bool = false, nameDraft: String = "", isSaving: Bool = false, cardError: String? = nil
    ) -> FriendsViewState {
        let entries = (board?.entries ?? []).sorted { $0.rank < $1.rank }
        let mineScore = entries.first { $0.isMe }?.card.overallScore
        let rows = entries.map { entry -> FriendsViewState.Row in
            let card = entry.card
            let name = entry.isMe ? "You" : card.displayName
            let compare = entry.isMe ? nil : compareText(theirs: card.overallScore, mine: mineScore)
            let growth = growthText(card.growthIndex)
            let spoken = [
                "Number \(entry.rank), \(name)",
                card.overallScore.map { "score \($0) out of 100" } ?? "no score yet",
                compare, growth, card.dataStatus == .mock ? "sample data" : nil,
            ].compactMap { $0 }.joined(separator: ". ")
            return .init(
                id: card.friendId, rank: entry.rank, name: name, isMe: entry.isMe, score: card.overallScore,
                scoreText: card.overallScore.map(String.init) ?? "-", growthText: growth, compareText: compare,
                isSample: card.dataStatus == .mock, spokenText: spoken
            )
        }
        let code = board?.myInviteCode ?? inviteCode
        let mineCard = myCard ?? entries.first { $0.isMe }?.card
        let preview = mineCard.map { detail(for: $0, isMe: true) }
        let savedName = mineCard?.displayName ?? ""
        let trimmed = nameDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        return FriendsViewState(
            phase: phase,
            rows: rows,
            friendCount: entries.filter { !$0.isMe }.count,
            inviteCode: code,
            explain: board?.explain ?? "",
            isSampleData: entries.contains { $0.card.dataStatus == .mock },
            banner: banner,
            details: entries.map { detail(for: $0.card, isMe: $0.isMe) },
            add: AddFriendState(
                inviteCode: code,
                inviteLink: "lifeline://join/\(code)",
                shareText: "Compare money habits with me on \(Brand.productName). Use my code \(code) or open lifeline://join/\(code). You only ever see scores, never amounts.",
                codeInput: codeInput, errorText: joinError, isJoining: isJoining, isRotating: isRotating
            ),
            mine: MyCardState(
                preview: preview, nameDraft: nameDraft, shareMix: mineCard?.mix != nil, isSaving: isSaving,
                errorText: cardError, canSaveName: !trimmed.isEmpty && trimmed != savedName && !isSaving
            )
        )
    }
}
