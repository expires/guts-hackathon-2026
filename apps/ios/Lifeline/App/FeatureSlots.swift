import SwiftUI

/// The root's only references to worker-owned screens (ADR 0037).
///
/// Each slot is one function. When a worker's screen lands, BOSS replaces the body of that one function.
/// Placeholders are views inside this file, so no worker type name is declared here.
///
/// | Slot | Worker | Final call |
/// |---|---|---|
/// | `onboarding` | W6 | `OnboardingScreen(client:startAt:onFinished:)` (`startAt` pending; until then `OnboardingScreen(client:onFinished:)`) |
/// | `account` | W6 | `AccountScreen(client:onSignedOut:onClose:)` |
/// | `penny` | W7 | `PennyScreen(client:context:onClose:onOpenLink:)` (live) |
@MainActor
enum FeatureSlots {
    @ViewBuilder
    static func onboarding(
        client: any LifelineClient,
        start: OnboardingStart,
        onFinished: @escaping @MainActor () -> Void
    ) -> some View {
        // Pending W6 `startAt:`. Then: OnboardingScreen(client: client, startAt: start == .connect ? .connect : .welcome, onFinished: onFinished)
        OnboardingScreen(client: client, onFinished: onFinished)
    }

    @ViewBuilder
    static func account(
        client: any LifelineClient,
        onSignedOut: @escaping @MainActor () -> Void,
        onClose: @escaping @MainActor () -> Void
    ) -> some View {
        AccountScreen(client: client, onSignedOut: onSignedOut, onClose: onClose)
    }

    @ViewBuilder
    static func penny(
        client: any LifelineClient,
        route: PennyRoute,
        onClose: @escaping @MainActor () -> Void,
        routes: AppRoutes
    ) -> some View {
        PennyScreen(
            client: client,
            context: pennyContext(route),
            onClose: onClose,
            onOpenLink: { _ in
                // next_move, test_it, why and plan all live on the Money tab.
                onClose()
                routes.selectTab(.money)
            }
        )
    }
}

extension FeatureSlots {
    /// App-side `PennyRoute` to W7's `PennyContext`. `.other` opens with the Money context.
    static func pennyContext(_ route: PennyRoute) -> PennyContext {
        let screen: PennyContext.Screen = switch route.screen {
        case .money, .other: .money
        case .nextMove: .nextMove
        case .why: .why
        case .lifeEvent: .lifeEvent
        case .life: .life
        }
        return PennyContext(
            screen: screen,
            nextMoveID: route.nextMoveID,
            lifeID: route.lifeID,
            eventID: route.eventID,
            question: route.question
        )
    }
}

/// Stand-in for a worker screen that has not landed yet.
private struct SlotPlaceholder: View {
    let title: String
    let message: String
    let onClose: @MainActor () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            Text(title).font(.llTitle)
            Text(message).font(.llBody).foregroundStyle(Theme.Palette.muted)
            Button("Close") { onClose() }
                .font(.llBodyBold)
                .frame(maxWidth: .infinity, minHeight: Theme.buttonHeight)
                .inkSurface(.button)
                .buttonStyle(.plain)
        }
        .padding(Theme.Spacing.margin)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .background(Theme.Palette.paper)
    }
}
