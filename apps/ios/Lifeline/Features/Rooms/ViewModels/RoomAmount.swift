import Foundation

/// Amount text for room screens that follows presentation mode (rounded, no pence).
/// Views pass `@Environment(\.llPresentationMode)`. The ViewStates carry raw numbers.
enum RoomAmount {
    static func shown(_ value: Double, presentation: Bool) -> Double {
        presentation ? LLAmountFormat.rounded(value) : value
    }

    static func compact(_ value: Double, presentation: Bool) -> String {
        LLAmountFormat(style: .compact, presentation: presentation).format(value)
    }

    static func standard(_ value: Double, presentation: Bool) -> String {
        LLAmountFormat(style: .standard, presentation: presentation).format(value)
    }

    /// VoiceOver reads the same value as the screen shows.
    static func spoken(_ value: Double, presentation: Bool) -> String {
        Money.spoken(shown(value, presentation: presentation))
    }
}
