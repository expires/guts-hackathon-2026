import Foundation

struct AssetsTabViewState: Equatable, Sendable {
    struct Item: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String
        var name: String
        var kindLabel: String
        var value: Double
    }

    var items: [Item]
    var totalValue: Double
    var actions: [ActionItemState]
    var isBusy: Bool
    var outcome: OutcomeState?
}
