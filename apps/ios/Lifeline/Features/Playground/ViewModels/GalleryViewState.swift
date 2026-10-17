import Foundation

struct GalleryViewState: Equatable, Sendable {
    struct Entry: Equatable, Sendable, Identifiable, Hashable {
        /// Stable id, for example "life.midLife". The glue maps it to a screen.
        var id: String
        var title: String
        var detail: String
    }

    struct Section: Equatable, Sendable, Identifiable {
        var id: String
        var title: String
        var entries: [Entry]
    }

    var title: String
    var sections: [Section]
}
