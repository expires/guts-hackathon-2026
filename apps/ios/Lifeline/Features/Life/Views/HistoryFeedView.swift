import SwiftUI

/// Year-by-year log, newest first.
struct HistoryFeedView: View {
    let history: [HistoryItemState]

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            Text("Your story")
                .font(.llScreenTitle)
                .accessibilityAddTraits(.isHeader)
            if history.isEmpty {
                Text("Nothing yet. Tap AGE to live your first year.")
                    .foregroundStyle(Theme.Palette.muted)
            } else {
                LazyVStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    ForEach(Array(history.enumerated().reversed()), id: \.offset) { offset, entry in
                        HistoryRow(entry: entry)
                            .accessibilityIdentifier("history.row.\(offset)")
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityIdentifier("history.feed")
    }
}

struct HistoryRow: View {
    let entry: HistoryItemState

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.m) {
            VStack(alignment: .leading) {
                Text(String(entry.year)).font(.llBodyBold.monospacedDigit())
                Text("Age \(entry.age)").font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
            .frame(minWidth: 56, alignment: .leading)
            Text(entry.text)
                .font(.llBody)
                .frame(maxWidth: .infinity, alignment: .leading)
            Text(Money.compact(entry.netWorth))
                .font(.llLabel.monospacedDigit())
                .foregroundStyle(entry.netWorth < 0 ? Theme.Palette.health : Theme.Palette.muted)
        }
        .padding(.vertical, Theme.Spacing.s)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(L10n.tr("\(String(entry.year)), age \(entry.age). \(entry.text) Net worth \(Money.spoken(entry.netWorth))."))
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Mid-life · light") {
    HistoryFeedView(history: Fixtures.LifeScreen.midLife.history).padding()
}

#Preview("Mid-life · dark") {
    HistoryFeedView(history: Fixtures.LifeScreen.midLife.history).padding().previewDark()
}

#Preview("Mid-life · AX3") {
    HistoryFeedView(history: Fixtures.LifeScreen.midLife.history).padding().previewLargeType()
}

#Preview("Empty · light") {
    HistoryFeedView(history: []).padding()
}

#Preview("Empty · dark") {
    HistoryFeedView(history: []).padding().previewDark()
}

#Preview("Empty · AX3") {
    HistoryFeedView(history: []).padding().previewLargeType()
}
