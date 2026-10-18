import SwiftUI

/// The root's only references to worker-owned screens (ADR 0037).
///
/// Each slot is one function. When a worker's screen lands, BOSS replaces the body of that one function.
/// Placeholders are views inside this file, so no worker type name is declared here.
///
/// | Slot | Worker | Final call |
/// |---|---|---|
/// | `onboarding` | W6 | `OnboardingScreen(client:startAt:onLanguage:onFinished:)` (live) |
/// | `account` | W6 | `AccountScreen(client:onSignedOut:onClose:)` |
/// | `language` | W6 | `LanguageScreen(onDone:)` (live) |
/// | `penny` | W7 | `PennyScreen(client:context:onClose:onOpenLink:)` (live) |
@MainActor
enum FeatureSlots {
    @ViewBuilder
    static func onboarding(
        client: any LifelineClient,
        start: OnboardingStart,
        onFinished: @escaping @MainActor () -> Void
    ) -> some View {
        OnboardingScreen(
            client: client,
            startAt: start == .connect ? .connect : .welcome,
            // Language Confirm (ADR 0063): save the app language; RootScreen switches the app live.
            onLanguage: { language in AppLanguage.set(language) },
            onFinished: onFinished
        )
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
            onOpenLink: { link in
                // Every link opens a Money screen: the forecast card or The maths (D5).
                onClose()
                routes.selectTab(.money)
                MoneyNavigation.shared.open(moneyDestination(link.destination))
            }
        )
    }

    /// Penny's link destination to the Money tab's navigation (W6 Money owns the push).
    static func moneyDestination(_ destination: PennyDestination) -> MoneyNavigation.Destination {
        switch destination {
        case .moneyForecast: .forecast
        case .theMaths: .theMaths
        }
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
        case .testIt: .testIt
        case .forecast: .forecast
        }
        return PennyContext(
            screen: screen,
            nextMoveID: route.nextMoveID,
            lifeID: route.lifeID,
            eventID: route.eventID,
            question: route.question,
            title: route.title
        )
    }
}

extension FeatureSlots {
    /// Language screen (ADR 0063), W6. It saves the choice with `AppLanguage.set`; the app switches live.
    @ViewBuilder
    static func language(onDone: @escaping @MainActor () -> Void) -> some View {
        LanguageScreen(onDone: onDone)
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
