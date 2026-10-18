import SwiftUI

/// "Ask Penny" as a sheet over a Life event or a room round (Ask Penny context fix).
///
/// The sheet stops below the top of the screen, so the event header and the room timer stay visible.
/// The screen behind stays live: the room timer keeps running and the player can still tap an option.
/// Closing the sheet returns to the same event. Each presentation is a NEW chat with its context.
///
/// ```swift
/// @State private var penny: PennyContext?
/// ...
/// .pennySheet($penny, client: session.client)
/// penny = PennyContext(screen: .lifeEvent, lifeID: life.id, eventID: event.id,
///                      question: PennyQuestion.lifeEvent, title: PennyContext.eventTitle(event.title, age: life.age))
/// ```
extension View {
    func pennySheet(_ context: Binding<PennyContext?>, client: any LifelineClient) -> some View {
        modifier(PennySheetModifier(context: context, service: .live(client)))
    }

    /// Tests and the Playground pass a scripted service.
    func pennySheet(_ context: Binding<PennyContext?>, service: PennyService) -> some View {
        modifier(PennySheetModifier(context: context, service: service))
    }
}

/// The sheet height: the top of the screen behind it (event header, room timer) stays visible.
enum PennySheetLayout {
    static let detent: PresentationDetent = .fraction(0.72)
}

private struct PennySheetModifier: ViewModifier {
    @Binding var context: PennyContext?
    let service: PennyService

    func body(content: Content) -> some View {
        content.sheet(item: $context) { value in
            PennyScreen(
                service: service,
                context: value,
                onClose: { context = nil },
                // Next Move, Test it, Why and plan links live on the Money tab. In a game they only close the sheet.
                onOpenLink: { _ in context = nil }
            )
            .paperBackground()
            .presentationDetents([PennySheetLayout.detent, .large])
            .presentationDragIndicator(.visible)
            .presentationBackground(Theme.Palette.paper)
            .presentationBackgroundInteraction(.enabled(upThrough: PennySheetLayout.detent))
            .accessibilityIdentifier("penny.sheet")
        }
    }
}
