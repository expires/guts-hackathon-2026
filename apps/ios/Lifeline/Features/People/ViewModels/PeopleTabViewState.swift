import Foundation

struct PeopleTabViewState: Equatable, Sendable {
    struct Person: Equatable, Sendable, Identifiable {
        var id: String
        var emoji: String
        var name: String
        var relation: String
        /// 0 to 100.
        var closeness: Int
    }

    var people: [Person]
    var actions: [ActionItemState]
    var isBusy: Bool
    var outcome: OutcomeState?
}
