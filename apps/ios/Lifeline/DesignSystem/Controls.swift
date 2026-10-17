import SwiftUI

// Own controls (no system List, Form, Picker, Stepper, Toggle or glass). Handoff style.

/// Sheet body: 24 pt title, our 44 pt close button, scrolling content.
/// Present it with `.llSheet(item:)` or `.llSheet(isPresented:)`: they add the paper, the hand-cut
/// 3 pt ink top edge and the dimmed backdrop. No system grabber, no glass.
struct SheetContainer<Content: View>: View {
    let title: String
    var closeIdentifier = "sheet.close"
    let onClose: () -> Void
    @ViewBuilder var content: Content

    var body: some View {
        VStack(spacing: 0) {
            ScreenHeader(title: title) {
                HeaderSquareButton(kind: .close, identifier: closeIdentifier, action: onClose)
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.l)
            .padding(.bottom, Theme.Spacing.m)
            ScrollView {
                VStack(alignment: .leading, spacing: Theme.Spacing.l) { content }
                    .padding(.horizontal, Theme.Spacing.margin)
                    .padding(.bottom, Theme.Spacing.xxl)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .scrollBounceBehavior(.basedOnSize)
        }
        .foregroundStyle(Theme.Palette.ink)
    }
}

/// Own sheet chrome: dimmed backdrop, then a paper card with hand-cut top corners and a 3 pt ink edge.
/// The card starts 8 pt under the status bar and runs to the bottom of the screen.
struct LLSheetFrame<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        content
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            .padding(.top, Theme.Spacing.xs)
            .background {
                ZStack {
                    HandCut.sheet.fill(Theme.Palette.paper)
                    HandCut.sheet.strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline)
                }
                .padding(.bottom, -Theme.Spacing.xxl)
                .ignoresSafeArea(edges: .bottom)
            }
            .padding(.top, Theme.Spacing.s)
            .background(Color.black.opacity(0.35).ignoresSafeArea())
    }
}

extension View {
    /// Own sheet (no system sheet, grabber or glass): full-screen cover with `LLSheetFrame`.
    func llSheet<Item: Identifiable, Sheet: View>(
        item: Binding<Item?>,
        @ViewBuilder content: @escaping (Item) -> Sheet
    ) -> some View {
        fullScreenCover(item: item) { value in
            LLSheetFrame { content(value) }.presentationBackground(.clear)
        }
    }

    /// Own sheet (no system sheet, grabber or glass): full-screen cover with `LLSheetFrame`.
    func llSheet<Sheet: View>(
        isPresented: Binding<Bool>,
        @ViewBuilder content: @escaping () -> Sheet
    ) -> some View {
        fullScreenCover(isPresented: isPresented) {
            LLSheetFrame { content() }.presentationBackground(.clear)
        }
    }

    /// Full screen with its own header (paper, no system chrome). For screens that are not sheets.
    func llCover<Item: Identifiable, Screen: View>(
        item: Binding<Item?>,
        @ViewBuilder content: @escaping (Item) -> Screen
    ) -> some View {
        fullScreenCover(item: item) { value in
            content(value).presentationBackground(Theme.Palette.paper)
        }
    }

    /// Full screen with its own header (paper, no system chrome). For screens that are not sheets.
    func llCover<Screen: View>(
        isPresented: Binding<Bool>,
        @ViewBuilder content: @escaping () -> Screen
    ) -> some View {
        fullScreenCover(isPresented: isPresented) {
            content().presentationBackground(Theme.Palette.paper)
        }
    }

    /// Deprecated: kept so older call sites compile. `.llSheet` draws the sheet chrome now.
    func llSheetPresentation(detents: Set<PresentationDetent> = [.large]) -> some View {
        self
    }

    /// Section eyebrow above a card: 13 bold, uppercase, muted.
    func sectionEyebrowStyle() -> some View {
        llEyebrow().foregroundStyle(Theme.Palette.muted)
    }
}

/// Outlined text field (17 pt, 52 pt tall).
struct LLTextField: View {
    let title: String
    @Binding var text: String
    var identifier = ""

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(title).font(.llLabelBold)
            TextField(title, text: $text)
                .font(.llBody)
                .padding(.horizontal, Theme.Spacing.m)
                .frame(minHeight: Theme.buttonHeight)
                .inkSurface(.buttonAlt)
                .accessibilityIdentifier(identifier)
        }
    }
}

/// Outlined pounds field.
struct LLMoneyField: View {
    let title: String
    @Binding var value: Double
    var identifier = ""

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            Text(title).font(.llLabelBold)
            TextField(title, value: $value, format: .currency(code: "GBP").locale(Money.locale).precision(.fractionLength(0)))
                .font(.llBody)
                .keyboardType(.numberPad)
                .padding(.horizontal, Theme.Spacing.m)
                .frame(minHeight: Theme.buttonHeight)
                .inkSurface(.buttonAlt)
                .accessibilityIdentifier(identifier)
        }
    }
}

/// − value + stepper with 52 pt buttons.
struct LLStepper: View {
    let title: String
    let valueText: String
    var canDecrement = true
    var canIncrement = true
    var identifier = ""
    let onDecrement: () -> Void
    let onIncrement: () -> Void

    var body: some View {
        HStack(spacing: Theme.Spacing.m) {
            stepButton("−", label: "Less", enabled: canDecrement, shape: HandCut((16, 20, 15, 19)), action: onDecrement)
            VStack(spacing: 2) {
                Text(title).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                Text(valueText).font(.llTitle).monospacedDigit()
            }
            .frame(maxWidth: .infinity)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(title)
            .accessibilityValue(valueText)
            .accessibilityAdjustableAction { direction in
                switch direction {
                case .increment: if canIncrement { onIncrement() }
                case .decrement: if canDecrement { onDecrement() }
                @unknown default: break
                }
            }
            .accessibilityIdentifier(identifier)
            stepButton("+", label: "More", enabled: canIncrement, shape: HandCut((20, 16, 19, 15)), action: onIncrement)
        }
        .padding(.horizontal, Theme.Spacing.m)
        .padding(.vertical, Theme.Spacing.s)
        .inkSurface(.card)
    }

    private func stepButton(_ text: String, label: String, enabled: Bool, shape: HandCut, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(text).font(.llTitle).frame(width: 52, height: 52).inkSurface(shape)
        }
        .buttonStyle(.plain)
        .foregroundStyle(Theme.Palette.ink)
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.4)
        .accessibilityLabel("\(label) \(title)")
    }
}

/// Single choice from a short list, shown as outlined chips. The chosen chip is ink-filled.
struct LLChoiceChips: View {
    struct Option: Identifiable, Equatable {
        var id: String
        var label: String
    }

    let title: String
    let options: [Option]
    let selection: String
    var identifier = ""
    let onSelect: (String) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            Text(title).font(.llLabelBold)
            FlowRow(spacing: Theme.Spacing.s) {
                ForEach(options) { option in
                    let isOn = option.id == selection
                    Button { onSelect(option.id) } label: {
                        Text(option.label)
                            .font(.llLabelBold)
                            .lineLimit(1)
                            .foregroundStyle(isOn ? Theme.Palette.surface : Theme.Palette.ink)
                            .padding(.horizontal, Theme.Spacing.m)
                            .frame(minHeight: Theme.minTarget)
                            .inkSurface(HandCut((10, 13, 9, 12)), fill: isOn ? Theme.Palette.ink : Theme.Palette.surface, lineWidth: Theme.chipOutline)
                    }
                    .buttonStyle(.plain)
                    .accessibilityAddTraits(isOn ? .isSelected : [])
                    .accessibilityIdentifier("\(identifier).\(option.id)")
                }
            }
        }
    }
}

/// Segmented control: equal outlined segments in one row, chosen one ink-filled.
struct LLSegmented: View {
    let options: [LLChoiceChips.Option]
    let selection: String
    let onSelect: (String) -> Void

    var body: some View {
        HStack(spacing: Theme.Spacing.xs) {
            ForEach(options) { option in
                let isOn = option.id == selection
                Button { onSelect(option.id) } label: {
                    Text(option.label)
                        .font(.llLabelBold)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                        .foregroundStyle(isOn ? Theme.Palette.surface : Theme.Palette.ink)
                        .frame(maxWidth: .infinity, minHeight: Theme.minTarget)
                        .inkSurface(HandCut((10, 13, 9, 12)), fill: isOn ? Theme.Palette.ink : Theme.Palette.surface, lineWidth: Theme.chipOutline)
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(isOn ? .isSelected : [])
            }
        }
    }
}

/// On/off switch row: label on the left, an outlined pill on the right.
struct LLToggleRow: View {
    let title: String
    var subtitle: String?
    let isOn: Bool
    var identifier = ""
    let onChange: (Bool) -> Void

    var body: some View {
        Button { onChange(!isOn) } label: {
            HStack(spacing: Theme.Spacing.m) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.llBodyBold)
                    if let subtitle { Text(subtitle).font(.llLabel).foregroundStyle(Theme.Palette.muted) }
                }
                Spacer()
                ZStack(alignment: isOn ? .trailing : .leading) {
                    Capsule().fill(isOn ? Theme.Palette.money : Theme.Palette.surface)
                        .overlay(Capsule().strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline))
                        .frame(width: 56, height: 32)
                    Circle().fill(Theme.Palette.ink).frame(width: 18, height: 18).padding(.horizontal, 8)
                }
            }
            .frame(minHeight: Theme.minTarget)
            .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .foregroundStyle(Theme.Palette.ink)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(title)
        .accessibilityValue(isOn ? "On" : "Off")
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier(identifier)
    }
}

/// Grouped rows inside one outlined card, with rule dividers between rows.
struct RowGroup<Content: View>: View {
    var title: String?
    var shape: HandCut = .card
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if let title { Text(title).sectionEyebrowStyle().accessibilityAddTraits(.isHeader) }
            VStack(spacing: 0) {
                Group(subviews: content) { subviews in
                    ForEach(Array(subviews.enumerated()), id: \.element.id) { offset, subview in
                        if offset > 0 { RuleDivider() }
                        subview.padding(.horizontal, Theme.Spacing.l)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .inkSurface(shape)
        }
    }
}

/// Eyebrow title above a group of rows.
struct RowGroupTitle: View {
    let text: String

    var body: some View {
        Text(text).sectionEyebrowStyle().accessibilityAddTraits(.isHeader)
    }
}

extension Binding {
    /// The same optional state, shown only for the values that match `include`.
    /// Lets one `@State` drive two presenters (for example `llSheet` and `llCover`).
    func only<Wrapped>(_ include: @escaping (Wrapped) -> Bool) -> Binding<Wrapped?> where Value == Wrapped? {
        Binding<Wrapped?>(
            get: { wrappedValue.flatMap { include($0) ? $0 : nil } },
            set: { newValue in
                if let newValue {
                    wrappedValue = newValue
                } else if let current = wrappedValue, include(current) {
                    wrappedValue = nil
                }
            }
        )
    }
}
