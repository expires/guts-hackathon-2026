import SwiftUI

/// Glue: owns `RealLifeDecisionViewModel` and feeds `RealLifeDecisionView`.
struct RealLifeDecisionScreen: View {
    @State private var model: RealLifeDecisionViewModel
    private let onClose: @MainActor () -> Void
    private let onTestIt: (@MainActor (String) -> Void)?

    /// Money tab, menus, or a "Play yourself" life that reached the present (`lifeID` set).
    init(client: any LifelineClient, profile: DecisionProfile, lifeID: String?, onClose: @escaping @MainActor () -> Void) {
        _model = State(initialValue: RealLifeDecisionViewModel(client: client, profile: profile, lifeID: lifeID))
        self.onClose = onClose
        self.onTestIt = nil
    }

    /// "Why?" on a mortgage Next Move (ADR 0018).
    /// - Parameters:
    ///   - character: the profile character from `GET /v1/finance/profile`.
    ///   - daysLeft: `Move.days_left`, sent as `deal_ends_in_months`.
    ///   - onTestIt: opens `TestItScreen(moveId:)` for `moveID`. Nil hides "Test it".
    init(
        client: any LifelineClient,
        moveID: String,
        character: CharacterSpec,
        daysLeft: Int?,
        currentYear: Int = Calendar(identifier: .gregorian).component(.year, from: .now),
        onTestIt: (@MainActor (String) -> Void)? = nil,
        onClose: @escaping @MainActor () -> Void
    ) {
        let profile = DecisionProfileMapping.profile(
            from: character,
            currentYear: currentYear,
            dealEndsInMonths: daysLeft.map(DecisionProfileMapping.months(fromDaysLeft:))
        )
        _model = State(initialValue: RealLifeDecisionViewModel(
            client: client, profile: profile, lifeID: nil, context: .whyMove, moveID: moveID
        ))
        self.onClose = onClose
        self.onTestIt = onTestIt
    }

    var body: some View {
        RealLifeDecisionView(state: model.state, actions: model.actions)
            .onAppear {
                model.onClose = onClose
                model.onTestIt = onTestIt
            }
            .task { await model.load() }
    }
}
