import Foundation

/// Icon and short name for each Next Move kind (contract `MoveKind`). Unknown kinds get a neutral style.
enum MoveKindStyle {
    static func systemImage(_ kind: String) -> String {
        switch kind {
        case "fix_mortgage", "remortgage": "house"
        case "move_savings": "banknote"
        case "cancel_subscription", "switch_subscription": "arrow.triangle.2.circlepath"
        case "switch_energy": "bolt"
        case "pay_off_debt": "creditcard"
        case "build_emergency_fund": "lifepreserver"
        case "cut_budget": "scissors"
        case "spread_isa": "chart.pie"
        default: "arrow.right.circle"
        }
    }

    /// Short plain English name. The move's own `action` text is still what the card shows.
    static func title(_ kind: String) -> String {
        switch kind {
        case "fix_mortgage": "Fix your mortgage"
        case "remortgage": "Switch your mortgage"
        case "move_savings": "Move your savings"
        case "cancel_subscription": "Cancel a subscription"
        case "switch_subscription": "Switch a subscription"
        case "switch_energy": "Switch your energy deal"
        case "pay_off_debt": "Pay off debt"
        case "build_emergency_fund": "Build a safety cushion"
        case "cut_budget": "Trim a budget"
        case "spread_isa": "Spread your ISA"
        default: kind.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }
}
