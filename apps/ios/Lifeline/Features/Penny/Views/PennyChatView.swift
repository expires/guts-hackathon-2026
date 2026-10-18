import SwiftUI

/// Ask Penny chat (ADR 0031, ADR 0051). User bubbles on the right, Penny on the left. Penny's face shows
/// once, next to her newest bubble. Each answer carries its mode label ("Checked with your data" or
/// "General answer"), tappable money and rates, follow-up chips and a collapsed "See sources" card.
struct PennyChatView: View {
    let state: PennyViewState
    var actions: PennyActions = .noop
    @State private var draft = ""
    @FocusState private var inputFocused: Bool
    @Namespace private var faceSpace
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    /// Width of Penny's face column, so bubbles without the face stay aligned.
    private let faceSize: CGFloat = 36

    var body: some View {
        VStack(spacing: 0) {
            header
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.top, Theme.Spacing.l)
                .padding(.bottom, Theme.Spacing.m)
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: Theme.Spacing.m) {
                        if state.isEmpty {
                            intro
                            if !state.chips.isEmpty { starterChips }
                        }
                        ForEach(state.rows) { row in
                            rowView(row).id(row.id)
                        }
                        Color.clear.frame(height: 1).id("penny.bottom")
                    }
                    .padding(.horizontal, Theme.Spacing.margin)
                    // Room above the first row, so a reaction badge is never clipped (fix 1).
                    .padding(.top, Theme.Spacing.l)
                    .padding(.bottom, Theme.Spacing.l)
                    .contentShape(.rect)
                    // Tap on the messages closes the keyboard (fix 7). Buttons still get their taps.
                    .simultaneousGesture(TapGesture().onEnded { inputFocused = false })
                }
                .defaultScrollAnchor(.bottom)
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: state.rows) { _, _ in scrollToBottom(proxy) }
                .onChange(of: inputFocused) { _, focused in
                    // The latest message stays above the input when the keyboard opens (fix 7).
                    if focused { scrollToBottom(proxy, delay: 0.3) }
                }
            }
            inputBar
        }
        .foregroundStyle(Theme.Palette.ink)
        .animation(Motion.standard(reduceMotion: reduceMotion), value: state.rows)
    }

    private func scrollToBottom(_ proxy: ScrollViewProxy, delay: Double = 0) {
        let scroll = { withAnimation(Motion.standard(reduceMotion: reduceMotion)) { proxy.scrollTo("penny.bottom", anchor: .bottom) } }
        if delay > 0 {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: scroll)
        } else {
            scroll()
        }
    }

    /// Penny's face for one row: shown only on the newest Penny row, and it moves down with it (fix 3).
    @ViewBuilder
    private func faceColumn(rowID: String, mood: PennyMood, thinking: Bool = false) -> some View {
        if state.pennyFaceRowID == rowID {
            PennyAnimatedFace(mood: self.mood(mood), thinking: thinking, size: faceSize)
                .matchedGeometryEffect(id: "penny.face", in: faceSpace)
                .accessibilityHidden(true)
        } else {
            Color.clear.frame(width: faceSize, height: 1)
        }
    }

    // MARK: Header and intro

    private var header: some View {
        ScreenHeader(
            title: state.title,
            leading: state.openThreadQuestionID == nil
                ? nil
                : HeaderSquareButton(kind: .back, identifier: "penny.thread.back", action: actions.onCloseThread)
        ) {
            if state.showsClose {
                HeaderSquareButton(kind: .close, identifier: "penny.close", action: actions.onClose)
            }
        }
    }

    private var intro: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            HStack(alignment: .top, spacing: 10) {
                PennyAnimatedFace(mood: .smiling, size: 44)
                Text(state.introText)
                    .font(.llBody)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .llChatBubble(.left)
            }
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("penny.intro")
            if !state.pastThreads.isEmpty {
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Text("Earlier chats").sectionEyebrowStyle()
                    VStack(spacing: 0) {
                        ForEach(Array(state.pastThreads.enumerated()), id: \.element.id) { index, thread in
                            if index > 0 { RuleDivider() }
                            Button { actions.onOpenPastThread(thread.id) } label: {
                                ListRow(icon: .why, title: thread.title, subtitle: thread.detail)
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("penny.past.\(thread.id)")
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.l)
                    .inkSurface(.card)
                }
            }
        }
    }

    // MARK: Rows

    @ViewBuilder
    private func rowView(_ row: PennyViewState.Row) -> some View {
        switch row {
        case let .question(question): questionView(question)
        case let .answer(group): answerView(group)
        case let .working(id, step): workingView(id: id, step: step)
        case let .failed(id, error): failedView(id: id, error: error)
        }
    }

    private func questionView(_ question: PennyViewState.Question) -> some View {
        VStack(alignment: .trailing, spacing: Theme.Spacing.xs) {
            HStack {
                Spacer(minLength: 56)
                Text(question.text)
                    .font(.llBody)
                    .foregroundStyle(Theme.Palette.onArea)
                    .fixedSize(horizontal: false, vertical: true)
                    .llChatBubble(.right, fill: Theme.Palette.work)
                    .overlay(alignment: .topLeading) {
                        if let reaction = question.reaction {
                            ReactionBadge(rawValue: reaction.rawValue)
                                .accessibilityIdentifier("penny.reaction.\(reaction.rawValue)")
                                .offset(x: -12, y: -16)
                                .transition(.scale.combined(with: .opacity))
                        }
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel(L10n.tr("You: \(question.text)"))
                    .accessibilityIdentifier("penny.question.\(question.id)")
            }
            // The badge sits 16 pt above the bubble: keep that room so it is never cut off (fix 1).
            .padding(.top, question.reaction == nil ? 0 : Theme.Spacing.l)
            if question.replyCount > 0 {
                Button { actions.onOpenThread(question.id) } label: {
                    Text(PennyMapping.repliesText(question.replyCount))
                        .font(.llLabelBold)
                        .foregroundStyle(Theme.Palette.accentText)
                        .frame(minHeight: Theme.minTarget)
                        .contentShape(.rect)
                }
                .buttonStyle(.plain)
                .accessibilityHint("Opens this question with its answers")
                .accessibilityIdentifier("penny.replies.\(question.id)")
            }
        }
        .frame(maxWidth: .infinity, alignment: .trailing)
    }

    private func answerView(_ group: PennyViewState.AnswerGroup) -> some View {
        HStack(alignment: .top, spacing: 10) {
            faceColumn(rowID: PennyViewState.Row.answer(group).id, mood: PennyMood.from(confidence: group.confidence))
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                if group.isComplete || !group.bubbles.isEmpty {
                    modeLabel(group)
                }
                ForEach(group.bubbles) { bubble in
                    bubbleView(bubble)
                        .transition(.opacity.combined(with: .move(edge: .bottom)))
                    if let open = state.openHighlightID, let detail = group.highlights[open], detail.bubbleID == bubble.id {
                        highlightCard(detail)
                    }
                }
                if group.isComplete {
                    if !group.isVerified {
                        Text("Short summary from the tools. Penny could not check a longer answer.")
                            .font(.llLabel).foregroundStyle(Theme.Palette.muted)
                            .accessibilityIdentifier("penny.unverified.\(group.id)")
                    }
                    if !group.links.isEmpty {
                        FlowRow(spacing: Theme.Spacing.s) {
                            ForEach(group.links, id: \.self) { link in
                                PennySmallButton(title: link.title, identifier: "penny.link.\(link.rawValue)") { actions.onLink(link) }
                            }
                        }
                    }
                    if !group.sourceGroups.isEmpty { sourcesCard(group) }
                    if state.suggestionsGroupID == group.id {
                        FlowRow(spacing: Theme.Spacing.s) {
                            ForEach(group.suggestions, id: \.self) { suggestion in
                                PennySmallButton(title: suggestion, identifier: "penny.suggestion", filled: true) { actions.onChip(suggestion) }
                                    .disabled(!state.canSend)
                            }
                        }
                        .accessibilityElement(children: .contain)
                        .accessibilityLabel("Follow-up questions")
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.trailing, Theme.Spacing.l)
    }

    /// "Checked with your data" (engine tool used) or "General answer" (ADR 0051).
    private func modeLabel(_ group: PennyViewState.AnswerGroup) -> some View {
        HStack(spacing: 6) {
            if group.isChecked { LLIconImage(.check, size: 24) }
            Text(group.modeLabel).font(.llLabelBold)
        }
        .foregroundStyle(group.isChecked ? Theme.Palette.ink : Theme.Palette.muted)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier(group.isChecked ? "penny.mode.checked" : "penny.mode.general")
    }

    private func bubbleView(_ bubble: PennyViewState.Bubble) -> some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            if bubble.kind == .generalKnowledge {
                Text("General knowledge").llEyebrow().foregroundStyle(Theme.Palette.muted)
            }
            Text(attributed(bubble))
                .font(.llBody)
                .tint(Theme.Palette.ink)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .llChatBubble(.left, fill: bubble.kind == .caveat ? Theme.Palette.paper : Theme.Palette.surface)
        .environment(\.openURL, OpenURLAction { url in
            guard url.scheme == "penny-number", let id = url.host() else { return .discarded }
            actions.onTapHighlight(id)
            return .handled
        })
        .accessibilityIdentifier("penny.bubble.\(bubble.id)")
    }

    /// Highlighted numbers are bold, underlined links ("penny-number://<highlight id>").
    private func attributed(_ bubble: PennyViewState.Bubble) -> AttributedString {
        var result = AttributedString()
        for segment in bubble.segments {
            var part = AttributedString(segment.text)
            if let id = segment.highlightID, let url = URL(string: "penny-number://\(id)") {
                part.link = url
                part.font = .llBodyBold
                part.underlineStyle = .single
                part.foregroundColor = Theme.Palette.ink
            }
            result += part
        }
        return result
    }

    private func highlightCard(_ detail: PennyViewState.HighlightDetail) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(alignment: .firstTextBaseline) {
                Text(detail.label).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                Spacer(minLength: Theme.Spacing.s)
                Text(detail.valueText).font(.llBodyBold)
            }
            if let source = detail.sourceLabel {
                HStack(spacing: 6) {
                    if let status = detail.status { LLIconImage(Theme.icon(for: status), size: 24) }
                    Text(source).font(.llLabelBold)
                }
            }
            if let updated = detail.updatedText {
                Text(updated).font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        }
        .padding(.horizontal, Theme.Spacing.m)
        .padding(.vertical, Theme.Spacing.s)
        .frame(maxWidth: 280, alignment: .leading)
        .inkSurface(.badge, lineWidth: Theme.chipOutline)
        .onTapGesture { actions.onTapHighlight(detail.id) }
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isButton)
        .accessibilityHint("Closes the number card")
        .accessibilityIdentifier("penny.highlight.card")
        .transition(.opacity)
    }

    private func sourcesCard(_ group: PennyViewState.AnswerGroup) -> some View {
        let expanded = state.expandedSourceGroups.contains(group.id)
        return VStack(alignment: .leading, spacing: 0) {
            Button { actions.onToggleSources(group.id) } label: {
                HStack {
                    Text(group.sourcesTitle).font(.llLabelBold)
                    Spacer()
                    Chevron().rotationEffect(.degrees(expanded ? 90 : 0))
                }
                .frame(minHeight: Theme.minTarget)
                .contentShape(.rect)
            }
            .buttonStyle(.plain)
            .accessibilityValue(expanded ? "Open" : L10n.tr("Closed, \(group.sourceGroups.reduce(0) { $0 + $1.rows.count }) sources"))
            .accessibilityIdentifier("penny.sources.\(group.id)")
            if expanded {
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    ForEach(group.sourceGroups) { sourceGroup in
                        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                            Text(sourceGroup.title).sectionEyebrowStyle()
                            ForEach(sourceGroup.rows) { row in
                                HStack(alignment: .top, spacing: 6) {
                                    if let status = row.status { LLIconImage(Theme.icon(for: status), size: 24) }
                                    VStack(alignment: .leading, spacing: 0) {
                                        Text(row.label).font(.llLabelBold)
                                        if let updated = row.updatedText {
                                            Text(updated).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                                        }
                                    }
                                }
                                .accessibilityElement(children: .combine)
                            }
                        }
                    }
                    RuleDivider()
                    Text(group.disclaimer)
                        .font(.llLabel)
                        .foregroundStyle(Theme.Palette.muted)
                        .accessibilityIdentifier("penny.disclaimer")
                }
                .padding(.bottom, Theme.Spacing.m)
            }
        }
        .padding(.horizontal, Theme.Spacing.m)
        .inkSurface(.cardAlt, lineWidth: Theme.chipOutline)
    }

    private func workingView(id: String, step: String?) -> some View {
        HStack(alignment: .top, spacing: 10) {
            faceColumn(rowID: PennyViewState.Row.working(id: id, step: step).id, mood: .thinking, thinking: true)
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                // The bubble hugs the three dots (fix 2).
                TypingDots()
                    .fixedSize()
                    .llChatBubble(.left)
                    .fixedSize()
                    .accessibilityIdentifier("penny.typing")
                ToolStepLine(step)
                    .accessibilityIdentifier("penny.step")
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("penny.working.\(id)")
    }

    private func failedView(id: String, error: ErrorViewState) -> some View {
        HStack(alignment: .top, spacing: 10) {
            faceColumn(rowID: PennyViewState.Row.failed(id: id, error: error).id, mood: .neutral)
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                Text(error.title).font(.llBodyBold)
                if !error.message.isEmpty {
                    Text(error.message).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                if error.canRetry {
                    PennySmallButton(title: "Try again", identifier: "penny.retry") { actions.onRetry(id) }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .llChatBubble(.left, fill: Theme.Palette.paper)
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("penny.failed.\(id)")
    }

    // MARK: Chips and input

    /// Starter questions: only on an empty chat, inside the chat area, never over messages (fix 8).
    private var starterChips: some View {
        FlowRow(spacing: Theme.Spacing.s) {
            ForEach(state.chips, id: \.self) { chip in
                PennySmallButton(title: chip, identifier: "penny.chip") { actions.onChip(chip) }
                    .disabled(!state.canSend)
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Suggested questions")
    }

    private var inputBar: some View {
        HStack(alignment: .bottom, spacing: Theme.Spacing.s) {
            TextField(state.inputPlaceholder, text: $draft, axis: .vertical)
                .font(.llBody)
                .lineLimit(1...4)
                .focused($inputFocused)
                .submitLabel(.send)
                .onSubmit(send)
                .padding(.horizontal, Theme.Spacing.m)
                .padding(.vertical, 12)
                .frame(minHeight: Theme.buttonHeight)
                .inkSurface(.buttonAlt)
                .accessibilityIdentifier("penny.input")
            Button("Send", action: send)
                .buttonStyle(MainButtonStyle())
                .frame(width: 88)
                .disabled(!state.canSend || draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .accessibilityIdentifier("penny.send")
        }
        .padding(.horizontal, Theme.Spacing.margin)
        .padding(.vertical, Theme.Spacing.m)
    }

    private func send() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard state.canSend, !text.isEmpty else { return }
        actions.onSend(text)
        draft = ""
        // Close the keyboard on send, so the answer is in view.
        inputFocused = false
    }

    private func mood(_ mood: PennyMood) -> PennyView.Mood {
        switch mood {
        case .happy: .happy
        case .thinking: .thinking
        case .neutral: .neutral
        case .smiling: .smiling
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Empty · light") { LLSheetFrame { PennyChatView(state: PennyFixtures.empty) } }
#Preview("Empty · dark") { LLSheetFrame { PennyChatView(state: PennyFixtures.empty) }.previewDark() }
#Preview("Thinking · light") { LLSheetFrame { PennyChatView(state: PennyFixtures.thinking) } }
#Preview("Streaming step · light") { LLSheetFrame { PennyChatView(state: PennyFixtures.streamingStep) } }
#Preview("Streaming step · dark") { LLSheetFrame { PennyChatView(state: PennyFixtures.streamingStep) }.previewDark() }
#Preview("Answer · light") { LLSheetFrame { PennyChatView(state: PennyFixtures.answer) } }
#Preview("Answer · dark") { LLSheetFrame { PennyChatView(state: PennyFixtures.answer) }.previewDark() }
#Preview("Answer · AX3") { LLSheetFrame { PennyChatView(state: PennyFixtures.answer) }.previewLargeType() }
#Preview("Sources open · light") { LLSheetFrame { PennyChatView(state: PennyFixtures.sourcesExpanded) } }
#Preview("Sources open · dark") { LLSheetFrame { PennyChatView(state: PennyFixtures.sourcesExpanded) }.previewDark() }
#Preview("Thread · light") { LLSheetFrame { PennyChatView(state: PennyFixtures.thread) } }
#Preview("Thread · AX3") { LLSheetFrame { PennyChatView(state: PennyFixtures.thread) }.previewLargeType() }
#Preview("Shrug · light") { LLSheetFrame { PennyChatView(state: PennyFixtures.shrug) } }
#Preview("Shrug · dark") { LLSheetFrame { PennyChatView(state: PennyFixtures.shrug) }.previewDark() }
#Preview("General answer · light") { LLSheetFrame { PennyChatView(state: PennyFixtures.general) } }
#Preview("General answer · dark") { LLSheetFrame { PennyChatView(state: PennyFixtures.general) }.previewDark() }
#Preview("Unavailable · light") { LLSheetFrame { PennyChatView(state: PennyFixtures.unavailable) } }
