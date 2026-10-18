import SwiftUI

/// Life as "Play solo" inside the Play tab (ADR 0048, 0052): character select when no life runs,
/// otherwise the running life. W9's `PlaySoloScreen` presents it.
///
/// - It never assumes it is a tab root: `onClose` puts a back button on character select and on
///   the running life, and returns to Play.
/// - The setup flow reports its depth through `SetupDepthKey`, so the root can still hide the tab
///   bar on the form and start-year screens.
struct LifeEntryScreen: View {
    let session: GameSession
    /// Back to Play. Nil (for example when Life is a root) hides the back buttons.
    var onClose: (@MainActor () -> Void)? = nil
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(session: GameSession, onClose: (@MainActor () -> Void)? = nil) {
        self.session = session
        self.onClose = onClose
    }

    var body: some View {
        Group {
            switch session.phase {
            case .selecting:
                LifeSelectionFlow(session: session, onClose: onClose)
                    .transition(.opacity)
            case .playing:
                LifeShellScreen(session: session, onExit: onClose)
                    .transition(.opacity)
            }
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: session.phase)
    }
}

/// Character select, then the optional form, then the start year. Same flow as the root's
/// `SelectionFlowScreen`, plus a back button to Play.
private struct LifeSelectionFlow: View {
    let session: GameSession
    let onClose: (@MainActor () -> Void)?
    @State private var path: [SelectionRoute] = []
    @State private var sheet: SelectionSheet?

    var body: some View {
        NavigationStack(path: $path) {
            CharacterSelectScreen(session: session, onClose: onClose) { route in
                switch route {
                case let .form(mode): path.append(.form(mode))
                case let .startYear(choice): path.append(.startYear(choice))
                case .store: break // The store is cut (ADR 0067).
                case .rooms: sheet = .rooms
                case .sources: sheet = .sources
                case .debugMenu: sheet = .debug
                }
            }
            .navigationDestination(for: SelectionRoute.self) { route in
                switch route {
                case let .form(mode):
                    CharacterFormScreen(mode: mode, session: session) { choice in path.append(.startYear(choice)) }
                case let .startYear(choice):
                    StartYearPickerScreen(choice: choice, session: session)
                }
            }
        }
        .preference(key: SetupDepthKey.self, value: path.count)
        .llCover(item: $sheet.only { $0 == .rooms }) { _ in
            RoomLobbyScreen(session: session) { self.sheet = nil }
        }
        .background {
            Color.clear.llSheet(item: $sheet.only { [.sources, .debug].contains($0) }) { sheet in
                let close: @MainActor () -> Void = { self.sheet = nil }
                switch sheet {
                case .debug: DebugMenuScreen(activeKind: session.client.kind, onClose: close)
                default: SourcesScreen(client: session.client, onClose: close)
                }
            }
        }
    }
}
