// Draft by W6. Owned by the UI owner from creation.
import Charts
import SwiftUI

/// How good the spend model is (ADR 0017): backtest error against a simple baseline, and range coverage.
struct SpendAccuracyView: View {
    let state: SpendAccuracyViewState
    var actions: SpendAccuracyActions = .noop

    var body: some View {
        SheetContainer(title: "How good is the model?", closeIdentifier: "accuracy.close", onClose: actions.onClose) {
            switch state.phase {
            case let .loading(loading):
                LoadingStateView(state: loading)
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                if state.isSampleData {
                    DemoDataBadge()
                    Text("These figures describe mock data, not your own spending.").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                InkCard(hero: true) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        Text(state.modelText).font(.llBodyBold)
                        Text(state.baselineText).font(.llBody)
                        Text(state.coverageText).font(.llBody)
                        Text(state.daysText).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    }
                }
                if !state.days.isEmpty {
                    Chart(state.days) { day in
                        RuleMark(x: .value("Day", day.dateText), yStart: .value("Low", day.low), yEnd: .value("High", day.high))
                            .foregroundStyle(Theme.Palette.rule)
                            .lineStyle(StrokeStyle(lineWidth: 6, lineCap: .round))
                        PointMark(x: .value("Day", day.dateText), y: .value("Predicted", day.predicted))
                            .foregroundStyle(Theme.Palette.work)
                        PointMark(x: .value("Day", day.dateText), y: .value("Actual", day.actual))
                            .foregroundStyle(Theme.Palette.money)
                            .symbol(.diamond)
                    }
                    .frame(height: 200)
                    .padding(Theme.Spacing.l)
                    .inkSurface(.card)
                    .accessibilityLabel("Predicted and actual spend per day")
                }
                Text(state.method).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") { SpendAccuracyView(state: Fixtures.SpendAccuracy.ready) }
#Preview("Ready · dark") { SpendAccuracyView(state: Fixtures.SpendAccuracy.ready).previewDark() }
#Preview("Ready · AX3") { SpendAccuracyView(state: Fixtures.SpendAccuracy.ready).previewLargeType() }
#Preview("Loading · light") { SpendAccuracyView(state: Fixtures.SpendAccuracy.loading) }
#Preview("Error · light") { SpendAccuracyView(state: Fixtures.SpendAccuracy.error) }
