import SwiftUI

/// Glue for "Where Penny's data comes from" (ADR 0073): owns `SourcesHubViewModel`, pushes a source's detail.
/// Push it inside a `NavigationStack` (Money home, The maths) or present it in one (You).
struct SourcesHubScreen: View {
    @State private var model: SourcesHubViewModel
    @Environment(\.dismiss) private var dismiss
    /// Nil: the back button pops the screen.
    private let onClose: (@MainActor () -> Void)?

    init(client: any LifelineClient, onClose: (@MainActor () -> Void)? = nil) {
        _model = State(initialValue: SourcesHubViewModel(client: client))
        self.onClose = onClose
    }

    var body: some View {
        SourcesHubView(state: model.state, actions: model.actions)
            .onAppear {
                let onClose = self.onClose
                let dismiss = self.dismiss
                model.onBack = { if let onClose { onClose() } else { dismiss() } }
            }
            .task { await model.load() }
            .navigationDestination(item: Binding(
                get: { model.selectedCard.map { CardRoute(card: $0) } },
                set: { if $0 == nil { model.selectedID = nil } }
            )) { route in
                SourceDetailView(card: route.card) { model.selectedID = nil }
            }
    }

    private struct CardRoute: Hashable, Identifiable {
        var card: SourcesHubViewState.Card
        var id: String { card.id }
        static func == (lhs: Self, rhs: Self) -> Bool { lhs.card.id == rhs.card.id }
        func hash(into hasher: inout Hasher) { hasher.combine(card.id) }
    }
}
