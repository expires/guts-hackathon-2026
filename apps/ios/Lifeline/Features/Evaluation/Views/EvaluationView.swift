// Draft by W6. Owned by the UI owner from creation.
import SwiftUI

/// Backtest of the decision engine (`/v1/evaluation`): how often its advice was right in past periods.
struct EvaluationView: View {
    let state: EvaluationViewState
    var actions: EvaluationActions = .noop

    var body: some View {
        SheetContainer(title: L10n.tr("How good is the advice?"), closeIdentifier: "evaluation.close", onClose: actions.onClose) {
            switch state.phase {
            case let .loading(loading):
                LoadingStateView(state: loading)
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                InkCard(hero: true) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        Text(state.hitText).font(.llTitle).accessibilityIdentifier("evaluation.hit")
                        InkProgressBar(value: state.hitRate, color: Theme.Palette.money)
                        Text(state.baselineText).font(.llBody)
                    }
                }
                RowGroup(title: L10n.tr("Past periods")) {
                    ForEach(state.periods) { period in
                        ListRow(icon: period.isHit ? .check : .statusMock, title: period.rangeText, subtitle: period.detail, showsChevron: false)
                            .accessibilityLabel(period.isHit
                                ? L10n.tr("\(period.rangeText). Right. \(period.detail)")
                                : L10n.tr("\(period.rangeText). Wrong. \(period.detail)"))
                    }
                }
                Text("\(state.method). \(state.generatedText).").font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") { EvaluationView(state: Fixtures.Evaluation.ready) }
#Preview("Ready · dark") { EvaluationView(state: Fixtures.Evaluation.ready).previewDark() }
#Preview("Ready · AX3") { EvaluationView(state: Fixtures.Evaluation.ready).previewLargeType() }
#Preview("Loading · light") { EvaluationView(state: Fixtures.Evaluation.loading) }
#Preview("Error · light") { EvaluationView(state: Fixtures.Evaluation.error) }
