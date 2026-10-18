import Foundation
import Observation

/// Lets other parts of the app (Penny links, ADR 0072) open a Money screen.
/// RootScreen switches to the Money tab, then calls `MoneyNavigation.shared.open(_:)`.
/// `MoneyHomeScreen` watches `request` and shows the screen.
@MainActor
@Observable
final class MoneyNavigation {
    enum Destination: Equatable, Sendable {
        /// Money home at the top, with the forecast card (pops any pushed Money screen).
        case forecast
        /// "The maths" pushed on Money home.
        case theMaths
        /// "All spending" pushed on Money home.
        case allSpending
    }

    static let shared = MoneyNavigation()

    /// The pending request. Money home clears it once handled. A new id makes a repeat request count.
    private(set) var request: (id: UUID, destination: Destination)?

    func open(_ destination: Destination) {
        request = (UUID(), destination)
    }

    func clear() {
        request = nil
    }
}
