import Foundation
import Observation

/// Lists every screen and fixture state for the Playground (`-playground`).
@MainActor
@Observable
final class GalleryViewModel {
    let state: GalleryViewState = GalleryViewModel.catalog

    /// The gallery list. Lives in `Fixtures` so previews do not read a ViewModel (UIR-4).
    static var catalog: GalleryViewState { Fixtures.galleryCatalog }
}
