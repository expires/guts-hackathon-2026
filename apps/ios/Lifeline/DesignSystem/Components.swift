import SwiftUI

// Components from `lifeline-design/screens/Style.dc.html`.

/// Card: surface fill, 3 pt ink outline, hand-cut corners. Never put a card inside a card.
struct InkCard<Content: View>: View {
    var shape: HandCut = .card
    var fill: Color = Theme.Palette.surface
    /// Offset shadow. Use on the hero element of a screen only.
    var hero = false
    var padding: CGFloat = Theme.Spacing.l
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .foregroundStyle(Theme.Palette.ink)
            .inkSurface(shape, fill: fill, hero: hero)
    }
}

/// Older name for `InkCard`. Kept so every screen gets the new look.
struct GlassCard<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        InkCard { content }
    }
}

/// Main button: ink fill, surface text, 52 pt.
struct MainButtonStyle: ButtonStyle {
    var shape: HandCut = .button

    func makeBody(configuration: Configuration) -> some View {
        StyledButton(configuration: configuration, shape: shape, fill: Theme.Palette.ink, text: Theme.Palette.surface)
    }
}

/// Second button: surface fill, ink text, 52 pt.
struct SecondButtonStyle: ButtonStyle {
    var shape: HandCut = .buttonAlt

    func makeBody(configuration: Configuration) -> some View {
        StyledButton(configuration: configuration, shape: shape, fill: Theme.Palette.surface, text: Theme.Palette.ink)
    }
}

/// Text button: underlined, 44 pt target.
struct TextButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.llBodyBold)
            .underline(true, pattern: .solid)
            .foregroundStyle(Theme.Palette.ink)
            .frame(minHeight: Theme.minTarget)
            .contentShape(.rect)
            .opacity(configuration.isPressed ? 0.6 : 1)
    }
}

private struct StyledButton: View {
    let configuration: ButtonStyleConfiguration
    let shape: HandCut
    let fill: Color
    let text: Color
    @Environment(\.isEnabled) private var isEnabled

    var body: some View {
        configuration.label
            .font(.llBodyBold)
            .foregroundStyle(text)
            .padding(.horizontal, Theme.Spacing.l)
            .frame(maxWidth: .infinity, minHeight: Theme.buttonHeight)
            .inkSurface(shape, fill: fill)
            .offset(x: configuration.isPressed ? 2 : 0, y: configuration.isPressed ? 2 : 0)
            .opacity(isEnabled ? 1 : 0.45)
    }
}

extension ButtonStyle where Self == MainButtonStyle {
    static var main: MainButtonStyle { MainButtonStyle() }
}

extension ButtonStyle where Self == SecondButtonStyle {
    static var second: SecondButtonStyle { SecondButtonStyle() }
}

extension ButtonStyle where Self == TextButtonStyle {
    static var text: TextButtonStyle { TextButtonStyle() }
}

/// Small chip with a 2 pt outline, for example "Up £3" (health) or "Saves £190" (money).
struct Chip: View {
    let text: String
    var fill: Color = Theme.Palette.surface
    var textColor: Color?

    var body: some View {
        Text(text)
            .font(.llLabelBold)
            .foregroundStyle(textColor ?? (fill == Theme.Palette.surface ? Theme.Palette.ink : Theme.Palette.onArea))
            .padding(.horizontal, Theme.Spacing.s)
            .padding(.vertical, 2)
            .inkSurface(.chip, fill: fill, lineWidth: Theme.chipOutline)
    }
}

/// Area chip: colour square plus the area word.
struct AreaChip: View {
    let area: Area
    var text: String?

    var body: some View {
        HStack(spacing: 6) {
            RoundedRectangle(cornerRadius: 3)
                .fill(area.color)
                .strokeBorder(Theme.Palette.ink, lineWidth: 2)
                .frame(width: 10, height: 10)
            Text(text ?? area.label).font(.llLabelBold)
        }
        .padding(.horizontal, Theme.Spacing.s)
        .padding(.vertical, 2)
        .inkSurface(HandCut((11, 8, 10, 7)), lineWidth: Theme.chipOutline)
    }
}

/// "Mock data" chip on any screen with fake data (handoff rule).
struct DemoDataBadge: View {
    var body: some View {
        Text("Mock data")
            .font(.llLabelBold)
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, 10)
            .padding(.vertical, 3)
            .inkSurface(.badge, lineWidth: Theme.chipOutline)
            .accessibilityLabel("Mock data. Not from your bank or the live server.")
            .accessibilityIdentifier("demoDataBadge")
    }
}

/// "Demo payment" label on every paid screen.
struct DemoPaymentLabel: View {
    var body: some View {
        HStack(spacing: 6) {
            LLIconImage(.demoPay, size: 24)
            Text(Brand.demoPaymentLabel).font(.llLabelBold)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 3)
        .inkSurface(.badge, fill: Theme.Palette.family, lineWidth: Theme.chipOutline)
        .foregroundStyle(Theme.Palette.onArea)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Demo payment. No real money is taken.")
        .accessibilityIdentifier("demoPaymentLabel")
    }
}

/// Large primary action (main style, 52 pt).
struct PrimaryButton: View {
    let title: String
    var icon: LLIcon?
    var isBusy = false
    let action: () -> Void

    init(title: String, icon: LLIcon? = nil, isBusy: Bool = false, action: @escaping () -> Void) {
        self.title = title
        self.icon = icon
        self.isBusy = isBusy
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.s) {
                if isBusy {
                    ProgressView().tint(Theme.Palette.surface)
                } else if let icon {
                    LLIconImage(icon, size: 24)
                }
                Text(title)
            }
        }
        .buttonStyle(.main)
    }
}

/// One 0 to 100 stat with an icon, a label and an outlined bar.
struct StatBar: View {
    let stat: StatState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Label(stat.kind.title, icon: Theme.icon(for: stat.kind))
                    .font(.llLabelBold)
                Spacer()
                Text("\(stat.value)%")
                    .font(.llLabelBold.monospacedDigit())
                    .contentTransition(.numericText(value: Double(stat.value)))
            }
            InkProgressBar(value: Double(stat.value) / 100, color: Theme.color(for: stat.kind))
                .animation(Motion.standard(reduceMotion: reduceMotion), value: stat.value)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(stat.kind.title)
        .accessibilityValue("\(stat.value) out of 100")
        .accessibilityIdentifier("stat.\(stat.kind.rawValue)")
    }
}

/// Outlined bar: 18 pt, 3 pt outline, coloured fill with an ink edge.
struct InkProgressBar: View {
    /// 0 to 1. Values above 1 fill the bar.
    let value: Double
    var color: Color = Theme.Palette.money
    var height: CGFloat = 18

    var body: some View {
        GeometryReader { proxy in
            let width = proxy.size.width * CGFloat(min(1, max(0, value)))
            ZStack(alignment: .leading) {
                Rectangle().fill(Theme.Palette.surface)
                Rectangle()
                    .fill(color)
                    .frame(width: width)
                    .overlay(alignment: .trailing) {
                        if width > 0 && value < 1 { Rectangle().fill(Theme.Palette.ink).frame(width: Theme.outline) }
                    }
            }
            .clipShape(HandCut.bar)
            .overlay(HandCut.bar.strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline))
        }
        .frame(height: height)
    }
}

/// Confidence meter: filled segments out of 3 (or more).
struct ConfidenceMeter: View {
    let filled: Int
    var total = 3

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<total, id: \.self) { index in
                HandCut([(5, 3, 6, 4), (3, 6, 4, 5), (6, 4, 5, 3)][index % 3])
                    .fill(index < filled ? Theme.Palette.ink : Color.clear)
                    .overlay(HandCut([(5, 3, 6, 4), (3, 6, 4, 5), (6, 4, 5, 3)][index % 3]).strokeBorder(Theme.Palette.ink, lineWidth: 2))
                    .frame(width: 28, height: 10)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(filled) of \(total)")
    }
}

/// List row: icon, title, line, chevron.
struct ListRow: View {
    let icon: LLIcon
    let title: String
    var subtitle: String?
    var trailing: String?
    var showsChevron = true

    var body: some View {
        HStack(spacing: Theme.Spacing.m) {
            LLIconImage(icon, size: 32)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.llBodyBold)
                if let subtitle {
                    Text(subtitle).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
            }
            Spacer(minLength: 0)
            if let trailing {
                Text(trailing).font(.llBodyBold.monospacedDigit())
            }
            if showsChevron { Chevron() }
        }
        .foregroundStyle(Theme.Palette.ink)
        .padding(.vertical, Theme.Spacing.m)
        .frame(minHeight: Theme.minTarget)
        .contentShape(.rect)
    }
}

/// Divider inside lists (rule colour, 2 pt).
struct RuleDivider: View {
    var body: some View {
        Rectangle().fill(Theme.Palette.rule).frame(height: 2)
    }
}

/// Penny the coin. Her face matches the confidence.
struct PennyView: View {
    enum Mood { case happy, thinking, neutral, smiling }
    var mood: Mood = .thinking
    var size: CGFloat = 64

    /// High (7 in 10 or more): happy. Medium (5 in 10 or more): thinking. Low: neutral.
    static func mood(confidence: Double) -> Mood {
        confidence >= 0.75 ? .happy : (confidence >= 0.5 ? .thinking : .neutral)
    }

    var body: some View {
        let icon: LLIcon = switch mood {
        case .happy: .pennyHappy
        case .thinking: .pennyThinking
        case .neutral: .pennyNeutral
        case .smiling: .pennySmiling
        }
        LLIconImage(icon, size: size)
    }
}

/// Shows where a number came from and how fresh it is: live, saved copy or sample.
struct SourceChip: View {
    let source: SourceChipState

    var body: some View {
        HStack(spacing: 6) {
            LLIconImage(Theme.icon(for: source.status), size: 24)
            Text(source.name).font(.llLabelBold)
            Text(source.status.label).font(.llLabel).foregroundStyle(Theme.Palette.muted)
        }
        .foregroundStyle(Theme.Palette.ink)
        .padding(.horizontal, Theme.Spacing.s)
        .frame(minHeight: 32)
        .inkSurface(HandCut((11, 8, 10, 7)), lineWidth: Theme.chipOutline)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Source \(source.name), \(source.status.label) data")
        .accessibilityIdentifier("sourceChip.\(source.id.split(separator: ".").first.map(String.init) ?? source.id)")
    }
}

/// Source chips plus any notes such as "UK average used".
struct SourcesFooter: View {
    let sources: [SourceChipState]

    private var notes: [String] {
        var seen = Set<String>()
        return sources.compactMap(\.note).filter { seen.insert($0).inserted }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.s) {
            Text("Where the numbers come from")
                .font(.llLabelBold)
                .foregroundStyle(Theme.Palette.muted)
            FlowRow(spacing: Theme.Spacing.s) {
                ForEach(sources) { SourceChip(source: $0) }
            }
            ForEach(notes, id: \.self) { note in
                Label(note, icon: .why)
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                    .accessibilityIdentifier("sourceNote")
            }
        }
    }
}

/// Simple wrapping row for chips.
struct FlowRow: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let rows = arrange(width: proposal.width ?? .infinity, subviews: subviews)
        let height = rows.map(\.height).reduce(0, +) + spacing * CGFloat(max(0, rows.count - 1))
        let width = rows.map(\.width).max() ?? 0
        return CGSize(width: proposal.width ?? width, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var y = bounds.minY
        for row in arrange(width: bounds.width, subviews: subviews) {
            var x = bounds.minX
            for index in row.indices {
                let size = subviews[index].sizeThatFits(.unspecified)
                subviews[index].place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
                x += size.width + spacing
            }
            y += row.height + spacing
        }
    }

    private struct Row {
        var indices: [Int] = []
        var width: CGFloat = 0
        var height: CGFloat = 0
    }

    private func arrange(width: CGFloat, subviews: Subviews) -> [Row] {
        var rows: [Row] = [Row()]
        for index in subviews.indices {
            let size = subviews[index].sizeThatFits(.unspecified)
            var row = rows[rows.count - 1]
            if !row.indices.isEmpty, row.width + spacing + size.width > width {
                rows.append(Row())
                row = Row()
            }
            row.width = row.indices.isEmpty ? size.width : row.width + spacing + size.width
            row.height = max(row.height, size.height)
            row.indices.append(index)
            rows[rows.count - 1] = row
        }
        return rows
    }
}

/// Screen background (paper) for full screens and sheets.
/// Also puts an opaque paper strip under the status bar, so scrolled content never shows under the clock.
extension View {
    func paperBackground() -> some View {
        background(Theme.Palette.paper.ignoresSafeArea())
            .safeAreaInset(edge: .top, spacing: 0) {
                Theme.Palette.paper.frame(height: 0).background(Theme.Palette.paper.ignoresSafeArea(edges: .top))
            }
    }
}

/// 44 pt square header button with a hand-cut outline: back chevron, close cross or an icon.
struct HeaderSquareButton: View {
    enum Kind { case back, close }
    let kind: Kind
    var icon: LLIcon?
    var label: String?
    var identifier = ""
    let action: () -> Void

    init(kind: Kind, identifier: String = "", action: @escaping () -> Void) {
        self.kind = kind
        self.identifier = identifier
        self.action = action
    }

    /// Icon button. A nil icon shows the back chevron. `label` is the VoiceOver label.
    init(icon: LLIcon?, label: String, identifier: String = "", action: @escaping () -> Void) {
        self.kind = .back
        self.icon = icon
        self.label = label
        self.identifier = identifier
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            Group {
                if let icon {
                    LLIconImage(icon, size: 28)
                } else {
                    switch kind {
                    case .back:
                        Chevron(direction: .left)
                    case .close:
                        Path { p in
                            p.move(to: CGPoint(x: 2, y: 2))
                            p.addLine(to: CGPoint(x: 14, y: 14))
                            p.move(to: CGPoint(x: 14, y: 2))
                            p.addLine(to: CGPoint(x: 2, y: 14))
                        }
                        .stroke(Theme.Palette.ink, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                        .frame(width: 16, height: 16)
                    }
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .frame(width: Theme.minTarget, height: Theme.minTarget)
            .inkSurface(HandCut((14, 18, 13, 17)))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label ?? (kind == .back ? "Back" : "Close"))
        .accessibilityIdentifier(identifier)
    }
}

/// Screen header: optional leading button, optional icon, 24 pt title, trailing view.
struct ScreenHeader<Trailing: View>: View {
    let title: String
    var icon: LLIcon?
    var leading: HeaderSquareButton?
    @ViewBuilder var trailing: Trailing

    var body: some View {
        HStack(spacing: Theme.Spacing.m) {
            if let leading { leading }
            if let icon { LLIconImage(icon, size: 32) }
            Text(title)
                .font(.llTitle)
                .foregroundStyle(Theme.Palette.ink)
                .frame(maxWidth: .infinity, alignment: .leading)
                .accessibilityAddTraits(.isHeader)
            trailing
        }
    }
}

extension ScreenHeader where Trailing == EmptyView {
    init(title: String, icon: LLIcon? = nil, leading: HeaderSquareButton? = nil) {
        self.title = title
        self.icon = icon
        self.leading = leading
        self.trailing = EmptyView()
    }
}
