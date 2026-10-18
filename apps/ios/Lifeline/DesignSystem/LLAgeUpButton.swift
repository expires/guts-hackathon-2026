import SwiftUI

/// The Age up button for Life (Play solo), Quick Life and Same Life rooms.
///
/// - Rounded pill, warm fill, 3 pt ink outline, the hard offset shadow of hero cards (`Theme.heroShadow`).
/// - Label "Age up → 19" with the cake inside the button, left of the text. `nextAge` comes from the engine
///   life state. Nil (the next age is not known, for example a Quick Life tap of 1 or 2 years) shows "Age up".
/// - Pressed: the button moves down onto its shadow and the shadow collapses, with a light haptic.
///   Reduce Motion: no movement, the shadow fades.
/// - Processing (a year is running): disabled, the cake pulses. Reduce Motion: the cake dims, no pulse.
/// - Disable it from outside with `.disabled(_:)` (event open, life over).
struct LLAgeUpButton: View {
    let nextAge: Int?
    var isProcessing = false
    /// VoiceOver hint, for example "Answer the open event first."
    var hint: String = ""
    let action: () -> Void

    @Environment(\.appLanguage) private var language

    var body: some View {
        Button(action: action) {
            LLAgeUpLabel(title: title, isProcessing: isProcessing)
        }
        .buttonStyle(LLAgeUpButtonStyle(isProcessing: isProcessing))
        .disabled(isProcessing)
        .accessibilityLabel(accessibilityTitle)
        .accessibilityHint(hint)
    }

    private var title: String {
        guard let nextAge else { return L10n.tr("Age up", language: language) }
        return L10n.tr("Age up → \(nextAge)", language: language)
    }

    private var accessibilityTitle: String {
        guard let nextAge else { return L10n.tr("Age up", language: language) }
        return L10n.tr("Age up to \(nextAge)", language: language)
    }
}

extension HandCut {
    /// Age up pill: corner radii of half the button height, slightly uneven for the hand-cut look.
    static let pill = HandCut((26, 28, 25, 27), (27, 25, 28, 26))
}

/// Cake medallion and title. The medallion keeps the cake readable on the warm fill in light and dark mode.
private struct LLAgeUpLabel: View {
    let title: String
    let isProcessing: Bool
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @ScaledMetric(relativeTo: .body) private var medallion: CGFloat = 34

    /// The medallion grows with Dynamic Type up to 48 pt; the cake keeps 5 pt of space on each side.
    private var side: CGFloat { min(medallion, 48) }

    var body: some View {
        HStack(spacing: Theme.Spacing.s) {
            cake
                .frame(width: side, height: side)
                .background(Circle().fill(Theme.Palette.surface))
                .overlay(Circle().strokeBorder(Theme.Palette.ink, lineWidth: Theme.chipOutline))
            Text(title)
                .lineLimit(2)
                .minimumScaleFactor(0.7)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    @ViewBuilder
    private var cake: some View {
        let icon = LLIconImage(.age, size: max(24, side - 10))
        if isProcessing && !reduceMotion {
            icon.phaseAnimator([false, true]) { content, up in
                content
                    .scaleEffect(up ? 1.15 : 0.9)
                    .opacity(up ? 1 : 0.6)
            } animation: { _ in .easeInOut(duration: 0.55) }
        } else {
            icon.opacity(isProcessing ? 0.5 : 1)
        }
    }
}

/// Press, disabled and processing looks for `LLAgeUpButton`.
struct LLAgeUpButtonStyle: ButtonStyle {
    var isProcessing = false

    func makeBody(configuration: Configuration) -> some View {
        LLAgeUpButtonBody(configuration: configuration, isProcessing: isProcessing)
    }
}

private struct LLAgeUpButtonBody: View {
    let configuration: ButtonStyleConfiguration
    let isProcessing: Bool
    @Environment(\.isEnabled) private var isEnabled
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var shape: HandCut { .pill }

    var body: some View {
        let pressed = configuration.isPressed && isEnabled
        let shadow = Theme.heroShadow
        let moves = pressed && !reduceMotion
        configuration.label
            .font(.llBodyBold)
            .foregroundStyle(Theme.Palette.onArea)
            .padding(.leading, Theme.Spacing.s)
            .padding(.trailing, Theme.Spacing.xl)
            .padding(.vertical, Theme.Spacing.s)
            .frame(minWidth: 180, minHeight: Theme.buttonHeight)
            .background {
                ZStack {
                    shape.fill(Theme.Palette.home)
                    shape.strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline)
                }
            }
            .offset(x: moves ? shadow.width : 0, y: moves ? shadow.height : 0)
            // The shadow stays in place; the face moves onto it when pressed.
            .background {
                shape.fill(Theme.Palette.ink)
                    .offset(x: shadow.width, y: shadow.height)
                    .opacity(pressed ? 0 : 1)
            }
            .contentShape(shape)
            .opacity(isEnabled || isProcessing ? 1 : 0.45)
            .animation(Motion.standard(reduceMotion: reduceMotion), value: pressed)
            .sensoryFeedback(.impact(weight: .light), trigger: pressed) { _, new in new }
    }
}

// MARK: - Previews (light, dark, large text, processing, disabled, languages)

private struct LLAgeUpPreviewBar: View {
    var nextAge: Int? = 19
    var isProcessing = false
    var isDisabled = false

    var body: some View {
        VStack(spacing: 0) {
            Spacer()
            LLAgeUpButton(nextAge: nextAge, isProcessing: isProcessing, hint: "Live one more year.") {}
                .disabled(isDisabled)
                .padding(.top, Theme.Spacing.m)
                .padding(.bottom, Theme.Spacing.l)
                .padding(.horizontal, Theme.Spacing.margin)
                .frame(maxWidth: .infinity)
                .background(Theme.Palette.surface)
                .overlay(alignment: .top) { Rectangle().fill(Theme.Palette.ink).frame(height: Theme.outline) }
        }
        .paperBackground()
    }
}

#Preview("Age up · light") { LLAgeUpPreviewBar() }
#Preview("Age up · dark") { LLAgeUpPreviewBar().previewDark() }
#Preview("Age up · AX3") { LLAgeUpPreviewBar().previewLargeType() }
#Preview("Age up · AX5") { LLAgeUpPreviewBar().environment(\.dynamicTypeSize, .accessibility5) }
#Preview("Processing · light") { LLAgeUpPreviewBar(isProcessing: true) }
#Preview("Processing · dark") { LLAgeUpPreviewBar(isProcessing: true).previewDark() }
#Preview("Disabled · light") { LLAgeUpPreviewBar(isDisabled: true) }
#Preview("Next age unknown · light") { LLAgeUpPreviewBar(nextAge: nil) }

#Preview("All languages · default") {
    VStack(spacing: Theme.Spacing.l) {
        ForEach(AppLanguage.allCases) { language in
            LLAgeUpButton(nextAge: 19) {}.environment(\.appLanguage, language)
        }
    }
    .padding(Theme.Spacing.margin)
    .paperBackground()
}

#Preview("All languages · AX3") {
    ScrollView {
        VStack(spacing: Theme.Spacing.l) {
            ForEach(AppLanguage.allCases) { language in
                LLAgeUpButton(nextAge: 19) {}.environment(\.appLanguage, language)
            }
        }
        .padding(Theme.Spacing.margin)
    }
    .paperBackground()
    .previewLargeType()
}
