import SwiftUI

/// "Play solo" (ADR 0052): W6's Life entry. Character or path choice, then the running life.
/// Both screens show a back button that closes this cover.
struct PlaySoloScreen: View {
    let session: GameSession
    let onClose: @MainActor () -> Void

    var body: some View {
        LifeEntryScreen(session: session, onClose: onClose)
            // Start, AGE, choice, action and rewind errors show here: the root alert sits under this cover.
            .sessionErrorAlert(session)
    }
}

/// Which presentation shows `GameSession.errorMessage`. An alert on a view under a full-screen cover or a
/// sheet cannot show, so only the top host (the last presentation that appeared) shows it.
/// The root alert shows only when no host is registered.
@MainActor
@Observable
final class SessionErrorHosts {
    static let shared = SessionErrorHosts()
    private(set) var stack: [UUID] = []

    func push(_ id: UUID) {
        stack.removeAll { $0 == id }
        stack.append(id)
    }

    func pop(_ id: UUID) {
        stack.removeAll { $0 == id }
    }

    /// True when `id` is the top host. A nil id is the root: true only when no presentation registered.
    func isTop(_ id: UUID?) -> Bool {
        guard let id else { return stack.isEmpty }
        return stack.last == id
    }
}

private struct SessionErrorAlert: ViewModifier {
    let session: GameSession
    var hosts = SessionErrorHosts.shared
    @State private var id = UUID()

    func body(content: Content) -> some View {
        content
            .onAppear { hosts.push(id) }
            .onDisappear { hosts.pop(id) }
            .alert(
                "Something went wrong",
                isPresented: Binding(
                    get: { session.errorMessage != nil && hosts.isTop(id) },
                    set: { if !$0 { session.errorMessage = nil } }
                ),
                presenting: session.errorMessage
            ) { _ in
                Button("OK", role: .cancel) { session.errorMessage = nil }
            } message: { message in
                Text(message)
            }
    }
}

extension View {
    /// Shows `session.errorMessage` from inside a cover or a sheet. Only the top presentation shows it.
    func sessionErrorAlert(_ session: GameSession) -> some View {
        modifier(SessionErrorAlert(session: session))
    }
}
