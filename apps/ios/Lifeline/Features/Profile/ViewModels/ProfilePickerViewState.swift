import Foundation

/// "Who are you playing as?": You (real data) and the sample students.
struct ProfilePickerViewState: Equatable, Sendable {
    struct Card: Equatable, Sendable, Identifiable {
        var id: String
        var title: String
        /// "Your own money", or the student's kind and age.
        var subtitle: String
        var detail: String?
        var avatar: String?
        var isYou: Bool
        var isActive: Bool
        /// "Sample data" on a sample student.
        var badge: String?
        /// True when the profile is a team phone profile.
        var isTeam = false
    }

    var phase: LoadPhase = .loading(.init(message: L10n.tr("Loading profiles")))
    var cards: [Card] = []
    /// The id being imported.
    var busyID: String?
    var errorMessage: String?
}

struct ProfilePickerActions {
    var onPick: (String) -> Void = { _ in }
    var onClose: () -> Void = {}
    var onRetry: () -> Void = {}
    var onDismissError: () -> Void = {}

    static var noop: Self { .init() }
}
