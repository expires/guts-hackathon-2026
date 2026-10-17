import SwiftUI

/// Playground gallery: every screen and fixture state.
struct GalleryView<Destination: View>: View {
    let state: GalleryViewState
    @ViewBuilder let destination: (String) -> Destination

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.xl) {
                    ScreenHeader(title: state.title)
                    ForEach(state.sections) { section in
                        RowGroup(title: section.title) {
                            ForEach(section.entries) { entry in
                                NavigationLink(value: entry) {
                                    HStack(spacing: Theme.Spacing.m) {
                                        VStack(alignment: .leading, spacing: 2) {
                                            Text(entry.title).font(.llBodyBold)
                                            Text(entry.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                        }
                                        Spacer(minLength: 0)
                                        Chevron()
                                    }
                                    .foregroundStyle(Theme.Palette.ink)
                                    .padding(.vertical, Theme.Spacing.s)
                                    .frame(minHeight: Theme.minTarget, alignment: .leading)
                                    .contentShape(.rect)
                                }
                                .buttonStyle(.plain)
                                .accessibilityIdentifier("gallery.\(entry.id)")
                            }
                        }
                    }
                }
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.vertical, Theme.Spacing.xl)
            }
            .paperBackground()
            .toolbar(.hidden, for: .navigationBar)
            .navigationDestination(for: GalleryViewState.Entry.self) { entry in
                destination(entry.id)
                    .navigationTitle(entry.detail)
                    .navigationBarTitleDisplayMode(.inline)
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Gallery · light") {
    GalleryView(state: GalleryViewModel.catalog) { id in Text(id) }
}

#Preview("Gallery · dark") {
    GalleryView(state: GalleryViewModel.catalog) { id in Text(id) }.previewDark()
}

#Preview("Gallery · AX3") {
    GalleryView(state: GalleryViewModel.catalog) { id in Text(id) }.previewLargeType()
}
