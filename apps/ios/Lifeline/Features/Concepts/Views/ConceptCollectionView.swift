import SwiftUI

/// Grid of concepts. Tap any concept to open its lesson (always free).
struct ConceptCollectionView: View {
    let state: ConceptCollectionViewState
    var actions: ConceptCollectionActions = .noop

    private let columns = [GridItem(.adaptive(minimum: 150), spacing: Theme.Spacing.m)]

    var body: some View {
        SheetContainer(title: "Concepts", closeIdentifier: "concepts.close", onClose: actions.onClose) {
            switch state.phase {
            case let .loading(loading):
                LoadingStateView(state: loading)
            case let .failed(error):
                ErrorStateView(state: error, onRetry: actions.onRetry)
            case .ready:
                Text("\(state.unlockedCount) of \(state.totalCount) unlocked")
                    .font(.llBodyBold)
                    .accessibilityIdentifier("concepts.count")
                VStack(spacing: Theme.Spacing.m) {
                    ForEach(state.items) { item in
                        Button { actions.onSelect(item.id) } label: {
                            HStack(alignment: .top, spacing: Theme.Spacing.m) {
                                LLIconImage(LLIcon.from(emoji: item.emoji, fallback: .lesson), size: 48)
                                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                                    Text(item.title).font(.llBodyBold).fixedSize(horizontal: false, vertical: true)
                                    Text(item.summary).font(.llLabel).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
                                    HStack(spacing: Theme.Spacing.s) {
                                        Chip(text: item.areaLabel)
                                        if !item.isUnlocked {
                                            Label("Not unlocked yet", icon: .lock).font(.llLabel)
                                        }
                                    }
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                Chevron()
                            }
                            .padding(Theme.Spacing.l)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .inkSurface(item.isUnlocked ? .card : .cardAlt, fill: item.isUnlocked ? Theme.Palette.surface : Theme.Palette.paper)
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(Theme.Palette.ink)
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel("\(item.title). \(item.summary). \(item.isUnlocked ? "Unlocked" : "Not unlocked yet")")
                        .accessibilityAddTraits(.isButton)
                        .accessibilityIdentifier("concept.\(item.id)")
                    }
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
