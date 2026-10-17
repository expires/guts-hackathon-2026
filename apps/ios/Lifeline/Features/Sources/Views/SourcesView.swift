import SwiftUI

/// Every data source, its freshness, coverage and licence.
struct SourcesView: View {
    let state: SourcesViewState
    var actions: SourcesActions = .noop

    var body: some View {
        NavigationStack {
            List {
                switch state.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    if state.usesSampleData {
                        DemoDataBadge()
                    }
                    Section {
                        ForEach(state.rows) { row in
                            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                                HStack {
                                    Text(row.name).font(.headline)
                                    Spacer()
                                    SourceChip(source: .init(id: row.id, name: row.status.label.capitalized, status: row.status))
                                }
                                Text("Covers \(row.coverage)").font(.subheadline)
                                if let updated = row.updatedText {
                                    Text(updated).font(.caption).foregroundStyle(.secondary)
                                }
                                Text("\(row.attribution). \(row.licence).").font(.caption).foregroundStyle(.secondary)
                                if row.status == .mock {
                                    Text(row.needsKey ? "Sample numbers. This source needs a free key on the server." : "Sample numbers.")
                                        .font(.caption)
                                        .foregroundStyle(.orange)
                                }
                            }
                            .padding(.vertical, Theme.Spacing.xs)
                            .accessibilityElement(children: .combine)
                            .accessibilityIdentifier("sources.row.\(row.id)")
                        }
                    } footer: {
                        Text("Live: fetched today. Saved copy: the last good download. Sample: example numbers while the source is not available.")
                    }
                }
            }
            .navigationTitle("Where our data comes from")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done", action: actions.onClose)
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
