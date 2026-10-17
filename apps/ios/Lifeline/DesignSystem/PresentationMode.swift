import SwiftUI

// Presentation mode: for showing the app on a big screen. Amounts are rounded and pence are hidden.
// Read it with `@Environment(\.llPresentationMode)`. Do not use SwiftUI's `presentationMode`.

extension EnvironmentValues {
    /// True when the app is shown to an audience. Amounts round (see `LLAmountFormat`).
    @Entry var llPresentationMode: Bool = false
}

/// How an amount is written.
enum LLAmountStyle: String, Codable, Sendable, Hashable {
    /// "£12,500". Whole pounds.
    case standard
    /// "+£600", "-£540".
    case signed
    /// "£950", "£12.5k", "-£1.2m".
    case compact
    /// "£4.20". Pence shown (presentation mode hides them).
    case pence
}

/// GBP format that follows presentation mode.
/// - Off: the style as written.
/// - On: under £1,000 rounds to the nearest £10, otherwise to the nearest £100. Never pence.
struct LLAmountFormat: FormatStyle, Sendable {
    var style: LLAmountStyle = .standard
    var presentation = false

    func format(_ value: Double) -> String {
        let shown = presentation ? Self.rounded(value) : value
        switch style {
        case .standard:
            return Money.format(shown)
        case .signed:
            return Money.signed(shown)
        case .compact:
            return Money.compact(shown)
        case .pence:
            if presentation { return Money.format(shown) }
            return shown.formatted(.currency(code: "GBP").locale(Money.locale).precision(.fractionLength(2)))
        }
    }

    /// Presentation rounding: nearest £10 under £1,000, nearest £100 from £1,000.
    static func rounded(_ value: Double) -> Double {
        let step: Double = abs(value) < 1_000 ? 10 : 100
        return (value / step).rounded() * step
    }
}

extension FormatStyle where Self == LLAmountFormat {
    /// `Text(amount, format: .llAmount(.signed, presentation: mode))` or `amount.formatted(.llAmount())`.
    static func llAmount(_ style: LLAmountStyle = .standard, presentation: Bool = false) -> LLAmountFormat {
        LLAmountFormat(style: style, presentation: presentation)
    }
}

/// Amount text that reads presentation mode from the environment.
/// VoiceOver reads the same rounded value as the screen shows.
struct LLAmount: View {
    let value: Double
    var style: LLAmountStyle = .standard
    @Environment(\.llPresentationMode) private var presentation

    init(_ value: Double, style: LLAmountStyle = .standard) {
        self.value = value
        self.style = style
    }

    var body: some View {
        let shown = presentation ? LLAmountFormat.rounded(value) : value
        Text(shown, format: .llAmount(style, presentation: presentation))
            .accessibilityLabel(Money.spoken(shown))
    }
}

extension View {
    /// Turns presentation mode on or off for this view and its children.
    func llPresentationMode(_ on: Bool) -> some View {
        environment(\.llPresentationMode, on)
    }
}

#Preview("Amounts") {
    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
        LLAmount(12_534.56)
        LLAmount(4.2, style: .pence)
        LLAmount(12_534.56).llPresentationMode(true)
        LLAmount(4.2, style: .pence).llPresentationMode(true)
    }
    .padding()
    .background(Theme.Palette.paper)
}
