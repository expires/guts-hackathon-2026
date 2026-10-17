import SwiftUI

/// Playground gallery: every screen and fixture state.
struct GalleryView<Destination: View>: View {
    let state: GalleryViewState
    @ViewBuilder let destination: (String) -> Destination

    var body: some View {
        NavigationStack {
            List {
                ForEach(state.sections) { section in
                    Section(section.title) {
                        ForEach(section.entries) { entry in
                            NavigationLink(value: entry) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(entry.title)
                                    Text(entry.detail).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                }
                                .frame(minHeight: Theme.minTarget, alignment: .leading)
                            }
                            .accessibilityIdentifier("gallery.\(entry.id)")
                        }
                    }
                }
            }
            .navigationTitle(state.title)
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
