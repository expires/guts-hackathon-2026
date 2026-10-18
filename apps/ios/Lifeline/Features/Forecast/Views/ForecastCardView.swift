import SwiftUI

/// The forecast card at the top of Money home (B3.1, canvas 1 and 2): chip, headline, next money,
/// the weekly figure, one habit line, the timeline, "See the maths" and "Ask Penny".
struct ForecastCardView: View {
    let state: ForecastCardState
    var onSeeMaths: () -> Void = {}
    var onAskPenny: () -> Void = {}

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    StatusChip(status: state.status, text: state.chipText)
                    Spacer(minLength: Theme.Spacing.s)
                    Text("This month").llEyebrow().font(ForecastFont.captionBold).foregroundStyle(Theme.Palette.muted)
                }
                Text(state.headline)
                    .font(ForecastFont.headline)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("forecast.headline")
                if let subline = state.subline {
                    Text(subline).font(ForecastFont.body).foregroundStyle(Theme.Palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, -4)
                }
                Rectangle().fill(Theme.Palette.ink).frame(height: 2).accessibilityHidden(true)
                if let note = state.budgetNote {
                    Text(note).font(ForecastFont.unit).fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("forecast.budgetNote")
                }
                if let lead = state.budgetLead, let weekly = state.weeklyAmount {
                    Text(lead).font(ForecastFont.bodyBold)
                    weeklyFigure(weekly).padding(.top, -6)
                }
                if let habit = state.habitLine {
                    Text(habit).font(ForecastFont.body).foregroundStyle(Theme.Palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(state.accessibilitySummary)
            .accessibilityIdentifier("forecast.summary")
            if !state.timeline.isEmpty {
                ForecastTimeline(points: state.timeline)
            }
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 10) { buttons }
                VStack(spacing: 10) { buttons }
            }
            .padding(.top, 4)
        }
        .padding(Theme.Spacing.xl)
        .frame(maxWidth: .infinity, alignment: .leading)
        .foregroundStyle(Theme.Palette.ink)
        .inkSurface(.hero, hero: true)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("forecast.card")
    }

    private func weeklyFigure(_ weekly: String) -> some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(weekly).font(ForecastFont.bigNumber).lineLimit(1)
                Text(state.unitText).font(ForecastFont.unit)
                if let daily = state.dailyText { Text(daily).font(ForecastFont.body).foregroundStyle(Theme.Palette.muted) }
            }
            VStack(alignment: .leading, spacing: 2) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(weekly).font(ForecastFont.bigNumber).lineLimit(1).minimumScaleFactor(0.6)
                    Text(state.unitText).font(ForecastFont.unit)
                }
                if let daily = state.dailyText { Text(daily).font(ForecastFont.body).foregroundStyle(Theme.Palette.muted) }
            }
        }
        .monospacedDigit()
        .contentTransition(.numericText())
        .accessibilityIdentifier("forecast.weekly")
    }

    @ViewBuilder
    private var buttons: some View {
        Button("See the maths", action: onSeeMaths)
            .buttonStyle(ForecastButtonStyle(filled: true))
            .accessibilityIdentifier("forecast.seeMaths")
        Button("Ask Penny", action: onAskPenny)
            .buttonStyle(ForecastButtonStyle(filled: false))
            .accessibilityIdentifier("forecast.askPenny")
    }
}

/// "On track" (green tint, tick) or "Running short" (orange tint, mark).
struct StatusChip: View {
    let status: ForecastCardState.Status
    let text: String

    var body: some View {
        HStack(spacing: 6) {
            Group {
                switch status {
                case .onTrack:
                    Path { p in
                        p.move(to: CGPoint(x: 2.5, y: 8))
                        p.addLine(to: CGPoint(x: 6.5, y: 12))
                        p.addLine(to: CGPoint(x: 13.5, y: 4))
                    }
                    .stroke(Theme.Palette.onArea, style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
                case .runningShort, .noNextMoney:
                    Path { p in
                        p.move(to: CGPoint(x: 8, y: 3))
                        p.addLine(to: CGPoint(x: 8, y: 9))
                        p.move(to: CGPoint(x: 8, y: 13))
                        p.addLine(to: CGPoint(x: 8, y: 13.2))
                    }
                    .stroke(Theme.Palette.onArea, style: StrokeStyle(lineWidth: 2.5, lineCap: .round))
                }
            }
            .frame(width: 16, height: 16)
            .accessibilityHidden(true)
            Text(text).font(.custom(LLFont.bodyBold, size: 14, relativeTo: .subheadline))
        }
        .foregroundStyle(Theme.Palette.onArea)
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
        .background(Capsule().fill(fill))
        .overlay(Capsule().strokeBorder(Theme.Palette.ink, lineWidth: 2))
        .accessibilityIdentifier("forecast.chip")
    }

    private var fill: Color {
        switch status {
        case .onTrack: Color(hex: 0xD5EEDD)
        case .runningShort: Color(hex: 0xFBE3C2)
        case .noNextMoney: Theme.Palette.other
        }
    }
}

/// Today, bills, run-out day and next money on one line (canvas timeline).
struct ForecastTimeline: View {
    let points: [ForecastCardState.Point]
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        Group {
            if typeSize.isAccessibilitySize {
                // Large text: one point per line, so nothing is cut.
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    ForEach(points) { point in
                        HStack(spacing: Theme.Spacing.s) {
                            dot(point)
                            Text(point.title).font(ForecastFont.captionBold)
                            Spacer(minLength: Theme.Spacing.s)
                            date(point)
                        }
                    }
                }
            } else {
                HStack(alignment: .top, spacing: 4) {
                    ForEach(points) { point in
                        VStack(spacing: 6) {
                            dot(point)
                            Text(point.title).font(ForecastFont.captionBold).multilineTextAlignment(.center)
                                .lineLimit(2).minimumScaleFactor(0.8)
                            date(point)
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
                .background(alignment: .top) {
                    GeometryReader { proxy in
                        let column = proxy.size.width / CGFloat(max(points.count, 1))
                        Rectangle().fill(Theme.Palette.ink)
                            .frame(width: max(0, proxy.size.width - column), height: 2)
                            .offset(x: column / 2, y: 6)
                    }
                    .accessibilityHidden(true)
                }
            }
        }
        .padding(.top, 4)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(points.map { "\($0.title), \($0.dateText)" }.joined(separator: ". "))
        .accessibilityIdentifier("forecast.timeline")
    }

    private func dot(_ point: ForecastCardState.Point) -> some View {
        let fill: Color = switch point.kind {
        case .today: Theme.Palette.ink
        case .bill: Theme.Palette.surface
        case .runOut: Theme.Palette.home
        case .nextMoney: Theme.Palette.money
        }
        return Circle().fill(fill)
            .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: 2))
            .frame(width: 14, height: 14)
    }

    private func date(_ point: ForecastCardState.Point) -> some View {
        Text(point.dateText)
            .font(point.kind == .runOut ? .custom(LLFont.bodyBold, size: 11, relativeTo: .caption2) : .custom(LLFont.body, size: 11, relativeTo: .caption2))
            .foregroundStyle(point.kind == .runOut ? ForecastPalette.runOutText : Theme.Palette.muted)
            .lineLimit(1)
    }
}

/// The canvas buttons: 48 pt, 3 pt outline, ink fill or white fill.
struct ForecastButtonStyle: ButtonStyle {
    var filled: Bool
    var height: CGFloat = 48

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(ForecastFont.bodyBold)
            .multilineTextAlignment(.center)
            .foregroundStyle(filled ? Theme.Palette.surface : Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.m)
            .frame(maxWidth: .infinity, minHeight: max(height, Theme.minTarget))
            .inkSurface(.button, fill: filled ? Theme.Palette.ink : Theme.Palette.surface)
            .offset(x: configuration.isPressed ? 2 : 0, y: configuration.isPressed ? 2 : 0)
    }
}

// MARK: - Previews

#Preview("On track · light") {
    ScrollView { ForecastCardView(state: ForecastFixtures.card(.onTrack)).padding(20) }.paperBackground()
}

#Preview("Running short · dark") {
    ScrollView { ForecastCardView(state: ForecastFixtures.card(.short)).padding(20) }.paperBackground().previewDark()
}

#Preview("On track · AX3") {
    ScrollView { ForecastCardView(state: ForecastFixtures.card(.onTrack)).padding(20) }.paperBackground().previewLargeType()
}
