import SwiftUI

/// A Money detail screen: own back button and title, then the detail sections.
struct MoneyDetailsView: View {
    let state: MoneyWidgetsViewState
    let detail: MoneyDetail
    var actions: MoneyWidgetsActions = .noop
    /// "Your next move: ..." back to the hub. Nil hides it.
    var nextMoveLink: MoveLinkState?
    var onBack: () -> Void = {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: detail.title, leading: HeaderSquareButton(kind: .back, identifier: "moneyDetail.back", action: onBack)) {
                    if state.isSampleData { DataBadge() }
                }
                if let link = nextMoveLink {
                    NextMoveLinkRow(text: link.text, action: onBack)
                }
                MoneyWidgetsView(state: state, actions: actions, detail: detail)
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s).padding(.bottom, Theme.Spacing.m)
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("All · light") { MoneyDetailsView(state: Fixtures.Widgets.ready, detail: .all) }
#Preview("All · dark") { MoneyDetailsView(state: Fixtures.Widgets.ready, detail: .all).previewDark() }
#Preview("All · AX3") { MoneyDetailsView(state: Fixtures.Widgets.ready, detail: .all).previewLargeType() }
#Preview("Net worth · light") { MoneyDetailsView(state: Fixtures.Widgets.ready, detail: .netWorth) }
#Preview("Accounts · light") { MoneyDetailsView(state: Fixtures.Widgets.ready, detail: .accounts) }
#Preview("Partial error · light") { MoneyDetailsView(state: Fixtures.Widgets.partialError, detail: .all) }
