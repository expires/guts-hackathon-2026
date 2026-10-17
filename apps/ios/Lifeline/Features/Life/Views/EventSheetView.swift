import SwiftUI

/// Full-screen event choice (handoff Life-Event): a colour band for the life area, the event icon,
/// the title and text, then one outlined card per choice with its monthly cost when the engine gives one.
struct EventSheetView: View {
    let state: EventSheetViewState
    var actions: EventSheetActions = .noop
    @Namespace private var namespace

    private var areaColor: Color { (Area(rawValue: state.area) ?? .other).color }
    private let cardShapes: [HandCut] = [HandCut((18, 24, 16, 22), (22, 16, 24, 18)), HandCut((24, 18, 22, 16), (16, 22, 18, 24))]

    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                band
                VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                    VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                        Text(state.title)
                            .font(.llTitle)
                            .accessibilityAddTraits(.isHeader)
                            .accessibilityIdentifier("event.title")
                        Text(state.text).font(.llBody).fixedSize(horizontal: false, vertical: true)
                        if state.isAIText {
                            Text("Words by AI. Numbers from the game engine.").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                    }
                    ForEach(Array(state.choices.enumerated()), id: \.element.id) { offset, choice in
                        choiceCard(choice, shape: cardShapes[offset % cardShapes.count])
                    }
                    if let onAskPenny = actions.onAskPenny {
                        Button(action: onAskPenny) {
                            HStack(spacing: Theme.Spacing.s) {
                                PennyView(mood: .thinking, size: 28)
                                Text("Not sure? Ask Penny")
                            }
                        }
                        .buttonStyle(.text)
                        .accessibilityIdentifier("event.askPenny")
                    }
                    if !state.sources.isEmpty {
                        SourcesFooter(sources: state.sources)
                    }
                }
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.top, Theme.Spacing.s).padding(.bottom, Theme.Spacing.m)
            }
        }
        .paperBackground()
        .foregroundStyle(Theme.Palette.ink)
    }

    private var band: some View {
        VStack(spacing: Theme.Spacing.m) {
            HStack {
                AreaChip(area: Area(rawValue: state.area) ?? .other, text: state.areaLabel)
                Spacer()
                Chip(text: state.dateText)
                HeaderSquareButton(kind: .close, identifier: "event.close", action: actions.onClose)
            }
            LLIconImage(LLIcon.from(emoji: state.emoji, fallback: Self.icon(for: state.area)), size: 120)
                .padding(.vertical, Theme.Spacing.s)
        }
        .padding(Theme.Spacing.margin)
        .frame(maxWidth: .infinity)
        .background(areaColor.ignoresSafeArea(edges: .top))
        .overlay(alignment: .bottom) { Rectangle().fill(Theme.Palette.ink).frame(height: Theme.outline) }
    }

    private func choiceCard(_ choice: EventSheetViewState.Choice, shape: HandCut) -> some View {
        let isChosen = state.chosenID == choice.id
        let isOther = state.chosenID != nil && !isChosen
        return Button { actions.onChoose(choice.id) } label: {
            HStack(spacing: Theme.Spacing.m) {
                VStack(alignment: .leading, spacing: 2) {
                    if isChosen {
                        HStack(spacing: Theme.Spacing.xs) {
                            LLIconImage(.check, size: 24)
                            Text("Chosen").font(.llLabelBold)
                        }
                        .accessibilityHidden(true)
                    }
                    Text(choice.label).font(.llBodyBold).fixedSize(horizontal: false, vertical: true)
                    if let hint = choice.hint {
                        Text(hint).font(.llLabel).foregroundStyle(Theme.Palette.muted).fixedSize(horizontal: false, vertical: true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if let amount = choice.amountText {
                    VStack(alignment: .trailing, spacing: 0) {
                        Text(amount).font(.llTitle).lineLimit(1).minimumScaleFactor(0.7)
                        if let caption = choice.amountCaption {
                            Text(caption).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                        }
                    }
                }
            }
            .padding(.horizontal, Theme.Spacing.l)
            .padding(.vertical, Theme.Spacing.m)
            .frame(minHeight: 76)
            .contentShape(shape)
            .background {
                ZStack {
                    if !isOther { shape.fill(Theme.Palette.ink).offset(x: isChosen ? 2 : 5, y: isChosen ? 3 : 6) }
                    shape.fill(isChosen ? Theme.Palette.money : Theme.Palette.surface)
                    shape.strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline)
                }
            }
        }
        .buttonStyle(.plain)
        // Ink text in every state: no system grey. The other choices dim but stay readable.
        .foregroundStyle(isChosen ? Theme.Palette.onArea : Theme.Palette.ink)
        .opacity(isOther ? 0.55 : 1)
        .allowsHitTesting(!state.isSubmitting)
        .accessibilityLabel([isChosen ? "Chosen" : nil, choice.label, choice.hint, choice.amountText.map { "\($0) a month" }].compactMap { $0 }.joined(separator: ". "))
        .accessibilityAddTraits(isChosen ? .isSelected : [])
        .accessibilityIdentifier("event.choice.\(choice.id)")
    }

    static func icon(for area: String) -> LLIcon {
        switch area {
        case "work": .job
        case "home": .home
        case "money": .savings
        case "family": .family
        case "health": .health
        default: .activities
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Rent rise · light") {
    EventSheetView(state: Fixtures.Event.rentRise)
}

#Preview("Rent rise · dark") {
    EventSheetView(state: Fixtures.Event.rentRise).previewDark()
}

#Preview("Rent rise · AX3") {
    EventSheetView(state: Fixtures.Event.rentRise).previewLargeType()
}

#Preview("Chosen · light") {
    EventSheetView(state: Fixtures.Event.chosen)
}

#Preview("Chosen · dark") {
    EventSheetView(state: Fixtures.Event.chosen).previewDark()
}

#Preview("Crisis · light") {
    EventSheetView(state: Fixtures.Event.crisis)
}

#Preview("Crisis · dark") {
    EventSheetView(state: Fixtures.Event.crisis).previewDark()
}

#Preview("Crisis · AX3") {
    EventSheetView(state: Fixtures.Event.crisis).previewLargeType()
}

#Preview("Submitting · light") {
    EventSheetView(state: Fixtures.Event.submitting)
}

#Preview("Submitting · dark") {
    EventSheetView(state: Fixtures.Event.submitting).previewDark()
}

#Preview("Submitting · AX3") {
    EventSheetView(state: Fixtures.Event.submitting).previewLargeType()
}
