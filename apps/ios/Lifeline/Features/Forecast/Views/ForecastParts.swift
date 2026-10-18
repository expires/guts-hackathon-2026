import SwiftUI

// View-local parts for the forecast and spending screens (ADR 0072, canvas "Penny Next Move: Will I make it?").

/// Colours from the canvas that the design system has no token for. Light and dark.
enum ForecastPalette {
    /// Green tint behind "On track", the sum and the save suggestion (#D5EEDD).
    static let greenTint = dynamic(light: 0xD5EEDD, dark: 0x1F3A2B)
    /// Orange tint behind "Running short" (#FBE3C2).
    static let orangeTint = dynamic(light: 0xFBE3C2, dark: 0x4A3518)
    /// Run-out date text (#A3480B), readable on white.
    static let runOutText = dynamic(light: 0xA3480B, dark: 0xFFB27A)
    /// Light grey for the 6th and later categories.
    static let rest = Theme.Palette.rule

    /// Category colour by rank: green, blue, orange, purple, grey, then light grey.
    static func slice(_ index: Int) -> Color {
        switch index {
        case 0: Theme.Palette.money
        case 1: Theme.Palette.work
        case 2: Theme.Palette.home
        case 3: Theme.Palette.family
        case 4: Theme.Palette.other
        default: rest
        }
    }

    private static func dynamic(light: UInt32, dark: UInt32) -> Color {
        Color(uiColor: UIColor { $0.userInterfaceStyle == .dark ? UIColor(hex: dark) : UIColor(hex: light) })
    }
}

/// Canvas type sizes on the app fonts. Each scales with Dynamic Type.
enum ForecastFont {
    /// 54, display: "£135".
    static var bigNumber: Font { LLFont.registerAll(); return .custom(LLFont.display, size: 54, relativeTo: .largeTitle) }
    /// 44, display: category total.
    static var total: Font { LLFont.registerAll(); return .custom(LLFont.display, size: 44, relativeTo: .largeTitle) }
    /// 32, display: "= £135 a week".
    static var sum: Font { LLFont.registerAll(); return .custom(LLFont.display, size: 32, relativeTo: .title) }
    /// 28, display: the headline.
    static var headline: Font { LLFont.registerAll(); return .custom(LLFont.display, size: 28, relativeTo: .title) }
    /// 26, display: screen titles and "Hi, Eilidh".
    static var screenTitle: Font { LLFont.registerAll(); return .custom(LLFont.display, size: 26, relativeTo: .title2) }
    /// 20, display: section titles.
    static var section: Font { LLFont.registerAll(); return .custom(LLFont.display, size: 20, relativeTo: .title3) }
    /// 18, display: breakdown section titles.
    static var smallSection: Font { LLFont.registerAll(); return .custom(LLFont.display, size: 18, relativeTo: .headline) }
    /// 20 bold: "a week".
    static var unit: Font { LLFont.registerAll(); return .custom(LLFont.bodyBold, size: 20, relativeTo: .title3) }
    /// 15 regular and bold: body text.
    static var body: Font { LLFont.registerAll(); return .custom(LLFont.body, size: 15, relativeTo: .subheadline) }
    static var bodyBold: Font { LLFont.registerAll(); return .custom(LLFont.bodyBold, size: 15, relativeTo: .subheadline) }
    /// 14 regular and bold: rows.
    static var row: Font { LLFont.registerAll(); return .custom(LLFont.body, size: 14, relativeTo: .subheadline) }
    static var rowBold: Font { LLFont.registerAll(); return .custom(LLFont.bodyBold, size: 14, relativeTo: .subheadline) }
    /// 12: captions and sources.
    static var caption: Font { LLFont.registerAll(); return .custom(LLFont.body, size: 12, relativeTo: .caption) }
    static var captionBold: Font { LLFont.registerAll(); return .custom(LLFont.bodyBold, size: 12, relativeTo: .caption) }
}

/// Back button and a 26 pt title (canvas screens 3 to 5).
struct ForecastScreenHeader: View {
    let title: String
    var identifier = "forecast.back"
    let onBack: () -> Void

    var body: some View {
        HStack(spacing: Theme.Spacing.m) {
            HeaderSquareButton(kind: .back, identifier: identifier, action: onBack)
            Text(title)
                .font(ForecastFont.screenTitle)
                .foregroundStyle(Theme.Palette.ink)
                .lineLimit(2)
                .minimumScaleFactor(0.8)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityAddTraits(.isHeader)
        }
    }
}

/// "Where your money goes      October so far".
struct ForecastSectionTitle: View {
    let title: String
    var trailing: String?

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .firstTextBaseline) {
                Text(title).font(ForecastFont.section)
                Spacer(minLength: Theme.Spacing.s)
                if let trailing { Text(trailing).font(.llLabel).foregroundStyle(Theme.Palette.muted).lineLimit(1) }
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(ForecastFont.section)
                if let trailing { Text(trailing).font(.llLabel).foregroundStyle(Theme.Palette.muted) }
            }
        }
        .foregroundStyle(Theme.Palette.ink)
        .padding(.top, 6)
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isHeader)
    }
}

/// White card with the 3 pt ink outline. `hero` adds the hard offset shadow.
struct ForecastCard<Content: View>: View {
    var fill: Color = Theme.Palette.surface
    var hero = false
    var padding: CGFloat = Theme.Spacing.l
    var spacing: CGFloat = 10
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: spacing) { content }
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .foregroundStyle(Theme.Palette.ink)
            .inkSurface(hero ? .hero : .card, fill: fill, hero: hero)
    }
}

/// A row button with a chevron: "See all spending", "See the detailed breakdown".
struct ForecastLinkRow: View {
    let title: String
    var identifier = ""
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack {
                Text(title).font(ForecastFont.bodyBold).frame(maxWidth: .infinity, alignment: .leading)
                Chevron()
            }
            .foregroundStyle(Theme.Palette.ink)
            .frame(minHeight: Theme.minTarget)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(identifier)
    }
}

/// Coloured dot with an ink ring, for the category legend.
struct CategoryDot: View {
    let color: Color

    var body: some View {
        Circle().fill(color)
            .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: 2))
            .frame(width: 12, height: 12)
            .accessibilityHidden(true)
    }
}

/// Donut chart with ink rings inside and outside, the total in the middle (canvas pies).
struct SpendingDonut: View {
    let slices: [SpendingSlice]
    let totalText: String
    let caption: String
    var size: CGFloat = 132
    var ring: CGFloat = 22
    /// VoiceOver label: "Spending by category, October so far".
    var label: String

    var body: some View {
        let total = slices.reduce(0) { $0 + $1.amount }
        let radius = (size - ring) / 2 - 6
        ZStack {
            if total > 0 {
                ForEach(Array(segments(total: total).enumerated()), id: \.offset) { _, segment in
                    Circle()
                        .trim(from: segment.start, to: segment.end)
                        .stroke(ForecastPalette.slice(segment.colorIndex), style: StrokeStyle(lineWidth: ring, lineCap: .butt))
                        .frame(width: radius * 2, height: radius * 2)
                        .rotationEffect(.degrees(-90))
                }
            } else {
                Circle().stroke(Theme.Palette.rule, lineWidth: ring).frame(width: radius * 2, height: radius * 2)
            }
            Circle().stroke(Theme.Palette.ink, lineWidth: 2.5).frame(width: radius * 2 + ring, height: radius * 2 + ring)
            Circle().stroke(Theme.Palette.ink, lineWidth: 2.5).frame(width: radius * 2 - ring, height: radius * 2 - ring)
            VStack(spacing: 0) {
                Text(totalText).font(.custom(LLFont.display, size: size * 0.16, relativeTo: .title2)).minimumScaleFactor(0.5).lineLimit(1)
                Text(caption).font(ForecastFont.caption).foregroundStyle(Theme.Palette.muted).lineLimit(1)
            }
            .frame(width: radius * 2 - ring - 8)
            .foregroundStyle(Theme.Palette.ink)
        }
        .frame(width: size, height: size)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(label)
        .accessibilityValue(slices.prefix(5).map { "\($0.label) \($0.amountText)" }.joined(separator: ", "))
    }

    private struct Segment { var start: Double; var end: Double; var colorIndex: Int }

    /// One segment per category, with a small gap between them like the canvas.
    private func segments(total: Double) -> [Segment] {
        var start = 0.0
        let gap = slices.count > 1 ? 0.006 : 0
        return slices.map { slice in
            let length = slice.amount / total
            defer { start += length }
            return Segment(start: start, end: max(start, start + length - gap), colorIndex: slice.colorIndex)
        }
    }
}

/// Skeleton in the shape of the forecast card (ADR 0060).
struct ForecastCardSkeleton: View {
    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            LLSkeleton(.line(width: 0.3, height: 22))
            LLSkeleton(.line(width: 0.85, height: 28))
            LLSkeleton(.line(width: 0.6))
            LLSkeleton(.line(width: 0.5, height: 48))
            LLSkeleton(.line(width: 0.9))
            LLSkeleton(.block(height: 40))
        }
        .padding(Theme.Spacing.xl)
        .frame(maxWidth: .infinity, alignment: .leading)
        .inkSurface(.hero, lineWidth: Theme.chipOutline)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Loading")
    }
}
