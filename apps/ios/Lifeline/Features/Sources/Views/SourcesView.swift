import SwiftUI

/// Every data source, its freshness, coverage and licence.
struct SourcesView: View {
    let state: SourcesViewState
    var actions: SourcesActions = .noop

    var body: some View {
        SheetContainer(title: "Where our data comes from", closeIdentifier: "sources.close", onClose: actions.onClose) {
            switch state.phase {
            case let .loading(loading):
                LoadingStateView(state: loading)
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                if state.usesSampleData { DemoDataBadge() }
                Text("Live: fetched today. Saved copy: the last good download. Sample: example numbers while the source is not available.")
                    .font(.llLabel).foregroundStyle(Theme.Palette.muted)
                RowGroup {
                    ForEach(state.rows) { row in
                        HStack(alignment: .top, spacing: Theme.Spacing.m) {
                            LLIconImage(Theme.icon(for: row.status), size: 32)
                            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                                HStack {
                                    Text(row.name).font(.llBodyBold)
                                    Spacer()
                                    Chip(text: row.status.label)
                                }
                                Text("Covers \(row.coverage)").font(.llLabel)
                                if let updated = row.updatedText {
                                    Text(updated).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                }
                                Text("\(row.attribution). \(row.licence).").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                if row.status == .mock {
                                    Text(row.needsKey ? "Sample numbers. This source needs a free key on the server." : "Sample numbers.")
                                        .font(.llLabelBold)
                                }
                            }
                        }
                        .padding(.vertical, Theme.Spacing.m)
                        .accessibilityElement(children: .combine)
                        .accessibilityIdentifier("sources.row.\(row.id)")
                    }
                }
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Ready · light") {
    SourcesView(state: Fixtures.Sources.ready)
}

#Preview("Ready · dark") {
    SourcesView(state: Fixtures.Sources.ready).previewDark()
}

#Preview("Ready · AX3") {
    SourcesView(state: Fixtures.Sources.ready).previewLargeType()
}

#Preview("Loading · light") {
    SourcesView(state: Fixtures.Sources.loading)
}

#Preview("Loading · dark") {
    SourcesView(state: Fixtures.Sources.loading).previewDark()
}

#Preview("Loading · AX3") {
    SourcesView(state: Fixtures.Sources.loading).previewLargeType()
}

#Preview("Error · light") {
    SourcesView(state: Fixtures.Sources.error)
}

#Preview("Error · dark") {
    SourcesView(state: Fixtures.Sources.error).previewDark()
}

#Preview("Error · AX3") {
    SourcesView(state: Fixtures.Sources.error).previewLargeType()
}
