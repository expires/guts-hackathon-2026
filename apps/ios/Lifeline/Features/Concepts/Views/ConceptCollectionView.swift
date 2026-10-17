import SwiftUI

/// Grid of concepts. Tap any concept to open its lesson (always free).
struct ConceptCollectionView: View {
    let state: ConceptCollectionViewState
    var actions: ConceptCollectionActions = .noop

    private let columns = [GridItem(.adaptive(minimum: 150), spacing: Theme.Spacing.m)]

    var body: some View {
        NavigationStack {
            ScrollView {
                switch state.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                        Text("\(state.unlockedCount) of \(state.totalCount) unlocked")
                            .font(.headline)
                            .accessibilityIdentifier("concepts.count")
                        LazyVGrid(columns: columns, spacing: Theme.Spacing.m) {
                            ForEach(state.items) { item in
                                Button { actions.onSelect(item.id) } label: {
                                    VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                                        Text(item.emoji).font(.largeTitle).accessibilityHidden(true)
                                        Text(item.title).font(.headline)
                                        Text(item.summary).font(.caption).foregroundStyle(.secondary).lineLimit(3)
                                        Text(item.areaLabel).font(.caption2).foregroundStyle(.tertiary)
                                    }
                                    .frame(maxWidth: .infinity, minHeight: 120, alignment: .topLeading)
                                    .opacity(item.isUnlocked ? 1 : 0.55)
                                }
                                .buttonStyle(.glass)
                                .accessibilityLabel("\(item.title). \(item.summary). \(item.isUnlocked ? "Unlocked" : "Not unlocked yet")")
                                .accessibilityIdentifier("concept.\(item.id)")
                            }
                        }
                    }
                    .padding(Theme.Spacing.l)
                }
            }
            .navigationTitle("Concepts")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done", action: actions.onClose)
                }
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Some unlocked · light") {
    ConceptCollectionView(state: Fixtures.Concepts.someUnlocked)
}

#Preview("Some unlocked · dark") {
    ConceptCollectionView(state: Fixtures.Concepts.someUnlocked).previewDark()
}

#Preview("Some unlocked · AX3") {
    ConceptCollectionView(state: Fixtures.Concepts.someUnlocked).previewLargeType()
}

#Preview("Loading · light") {
    ConceptCollectionView(state: Fixtures.Concepts.loading)
}

#Preview("Loading · dark") {
    ConceptCollectionView(state: Fixtures.Concepts.loading).previewDark()
}

#Preview("Loading · AX3") {
    ConceptCollectionView(state: Fixtures.Concepts.loading).previewLargeType()
}

#Preview("Error · light") {
    ConceptCollectionView(state: Fixtures.Concepts.error)
}

#Preview("Error · dark") {
    ConceptCollectionView(state: Fixtures.Concepts.error).previewDark()
}

#Preview("Error · AX3") {
    ConceptCollectionView(state: Fixtures.Concepts.error).previewLargeType()
}
