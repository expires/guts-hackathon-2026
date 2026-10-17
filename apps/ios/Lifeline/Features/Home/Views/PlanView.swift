// Draft by W6. Owned by the UI owner from creation.
import SwiftUI

/// The user's plan: moves chosen with "Do this" (ADR 0018).
struct PlanView: View {
    let state: PlanViewState
    var actions: PlanActions = .noop

    var body: some View {
        SheetContainer(title: "Your plan", closeIdentifier: "plan.close", onClose: actions.onClose) {
            switch state.phase {
            case let .loading(loading):
                LoadingStateView(state: loading)
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                if state.isSampleData { DemoDataBadge() }
                if !state.items.isEmpty {
                    RowGroup {
                        ForEach(state.items) { item in
                            ListRow(icon: item.isDone ? .check : .goal, title: item.action, subtitle: "\(item.impactText). \(item.addedText)", showsChevron: false)
                                .accessibilityIdentifier("plan.item.\(item.id)")
                        }
                    }
                }
                Text(state.totalText).font(.llBodyBold).accessibilityIdentifier("plan.total")
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("One item · light") { PlanView(state: Fixtures.Plan.oneItem) }
#Preview("One item · dark") { PlanView(state: Fixtures.Plan.oneItem).previewDark() }
#Preview("One item · AX3") { PlanView(state: Fixtures.Plan.oneItem).previewLargeType() }
#Preview("Empty · light") { PlanView(state: Fixtures.Plan.empty) }
#Preview("Loading · light") { PlanView(state: Fixtures.Plan.loading) }
#Preview("Error · light") { PlanView(state: Fixtures.Plan.error) }
