import Foundation

/// Friends tab: a leaderboard of habit scores, a way to add friends and a preview of what they see.
/// Scores and percentages only. Amounts never appear here.
struct FriendsViewState: Equatable, Sendable {
    struct Row: Equatable, Sendable, Identifiable {
        var id: String
        var rank: Int
        var name: String
        var isMe: Bool
        /// 0 to 100. Nil when there is no score yet.
        var score: Int?
        /// "72", or "-" without a score.
        var scoreText: String
        /// "Investments: 112, started at 100". Nil when they have no growth number.
        var growthText: String?
        /// "8 points above you". Nil for your own row or when a score is missing.
        var compareText: String?
        var isSample: Bool
        var spokenText: String
    }

    struct Banner: Equatable, Sendable {
        enum Kind: Equatable, Sendable { case success, failure }
        var kind: Kind
        var text: String
    }

    var phase: LoadPhase
    var rows: [Row]
    /// People on the board other than you.
    var friendCount: Int
    var inviteCode: String
    var explain: String
    var isSampleData: Bool
    var banner: Banner?
    var details: [FriendDetailState]
    var add: AddFriendState
    var mine: MyCardState

    func detail(id: String) -> FriendDetailState? { details.first { $0.id == id } }
    var hasGrowth: Bool { rows.contains { $0.growthText != nil } }
}

/// One person's card as friends see it: score, habit factors, and the mix when shared.
struct FriendDetailState: Equatable, Sendable, Identifiable {
    struct Factor: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var score: Int
        var scoreText: String
        var bandText: String
    }

    struct Slice: Equatable, Sendable, Identifiable {
        var id: String
        var label: String
        var percent: Double
        var percentText: String
    }

    var id: String
    var name: String
    var isMe: Bool
    var score: Int?
    var scoreText: String
    var bandText: String?
    var growthText: String?
    var factors: [Factor]
    var slices: [Slice]
    /// Why there is no donut, for example "Sam has not shared their mix."
    var mixNote: String?
    var isSample: Bool
}

struct AddFriendState: Equatable, Sendable {
    static let codeLength = 8
    var inviteCode: String
    /// "lifeline://join/K7M2QX9P"
    var inviteLink: String
    var shareText: String
    var codeInput: String
    var errorText: String?
    var isJoining: Bool
    var isRotating: Bool
    var canJoin: Bool { codeInput.count == Self.codeLength && !isJoining }
}

struct MyCardState: Equatable, Sendable {
    var preview: FriendDetailState?
    /// What is typed in the name field.
    var nameDraft: String
    var shareMix: Bool
    var isSaving: Bool
    var errorText: String?
    var canSaveName: Bool
}

struct FriendsActions {
    var onRetry: @MainActor () -> Void = {}
    var onSelect: @MainActor (String) -> Void = { _ in }
    var onOpenAdd: @MainActor () -> Void = {}
    var onOpenMine: @MainActor () -> Void = {}
    var onRemove: @MainActor (String) -> Void = { _ in }
    var onDismissBanner: @MainActor () -> Void = {}
    // Add a friend
    var onCodeChange: @MainActor (String) -> Void = { _ in }
    var onJoin: @MainActor () -> Void = {}
    var onRotate: @MainActor () -> Void = {}
    var onCopied: @MainActor () -> Void = {}
    // What friends see
    var onNameChange: @MainActor (String) -> Void = { _ in }
    var onSaveName: @MainActor () -> Void = {}
    var onShareMix: @MainActor (Bool) -> Void = { _ in }

    static var noop: Self { .init() }
}
