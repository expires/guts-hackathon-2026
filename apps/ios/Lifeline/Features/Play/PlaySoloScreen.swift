import SwiftUI

/// "Play solo" (ADR 0052): W6's Life entry. Character or path choice, then the running life.
/// Both screens show a back button that closes this cover.
struct PlaySoloScreen: View {
    let session: GameSession
    let onClose: @MainActor () -> Void

    var body: some View {
        LifeEntryScreen(session: session, onClose: onClose)
    }
}
