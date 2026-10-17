import Foundation

/// Labelled sample friends for `MockClient`, fixtures and the Playground. Everything here is made up.
/// Cards carry scores and percentages only, never amounts.
enum SampleFriends {
    static let stamp = "2026-10-17T00:00:00Z"
    static let myID = "fr_mock_me00000000"
    static let myCode = "K7M2QX9P"
    static let myScore = 67

    static func card(
        id: String, name: String, score: Int?, factors: [String: Int], growth: Double?,
        mix: [String: Double]? = nil
    ) -> FriendCard {
        FriendCard(
            friendId: id, displayName: name, overallScore: score,
            factorScores: .init(additionalProperties: factors),
            growthIndex: growth,
            mix: mix.map { .init(additionalProperties: $0) },
            dataStatus: .mock, updatedAt: stamp
        )
    }

    static func me(name: String = "You", shareMix: Bool = false) -> FriendCard {
        card(
            id: myID, name: name, score: myScore,
            factors: [
                "savings_rate": 70, "runway_months": 58, "spend_stability": 76, "discretionary_share": 52,
                "subscription_creep": 81, "shock_resilience": 64,
            ],
            growth: 108.4,
            mix: shareMix ? ["equity": 80.9, "bond": 14.0, "commodity": 5.1] : nil
        )
    }

    static let sam = card(
        id: "fr_mock_sam0000000", name: "Sam", score: 75,
        factors: ["savings_rate": 82, "runway_months": 70, "spend_stability": 68, "discretionary_share": 61, "subscription_creep": 77],
        growth: 112.0,
        mix: ["equity": 70.0, "bond": 20.0, "cash": 10.0]
    )
    static let priya = card(
        id: "fr_mock_priya00000", name: "Priya", score: 61,
        factors: ["savings_rate": 58, "runway_months": 49, "spend_stability": 72, "shock_resilience": 55],
        growth: 104.7
    )
    static let alex = card(
        id: "fr_mock_alex000000", name: "Alex", score: 48,
        factors: ["savings_rate": 41, "runway_months": 36, "discretionary_share": 44],
        growth: nil
    )

    /// Friends you start with in the mock.
    static let initialFriends: [FriendCard] = [sam, priya, alex]

    /// A friend who can be added with this code in the mock.
    static let joinable: [String: FriendCard] = [
        "PQ7WXR3N": card(
            id: "fr_mock_jo00000000", name: "Jo", score: 70,
            factors: ["savings_rate": 66, "runway_months": 74, "spend_stability": 71],
            growth: 109.3, mix: ["equity": 60.0, "bond": 40.0]
        )
    ]

    static func leaderboard(me: FriendCard, friends: [FriendCard], code: String) -> Leaderboard {
        let all = ([me] + friends).sorted { ($0.overallScore ?? -1) > ($1.overallScore ?? -1) }
        let entries = all.enumerated().map { offset, card in
            LeaderboardEntry(
                card: card, rank: offset + 1, isMe: card.friendId == me.friendId,
                scoreVsMe: {
                    guard let mine = me.overallScore, mine > 0, let theirs = card.overallScore else { return nil }
                    return Double(theirs) / Double(mine) * 100
                }()
            )
        }
        return Leaderboard(
            entries: entries, myInviteCode: code,
            explain: "Growth is how an investment mix would have grown, shown as 100 at the start, so 150 means it grew by half. Friends are compared on the same scale, with no money amounts."
        )
    }
}
