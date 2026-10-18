// Draft by W9. "Type a code instead" from the Play tab Join button (ADR 0052).
import SwiftUI

/// Small screen: type a 6-character room code and join.
struct RoomCodeEntryView: View {
    let state: RoomEntryViewState
    var actions: RoomEntryActions = .noop
    var onClose: () -> Void = {}
    @FocusState private var focused: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            ScreenHeader(title: L10n.tr("Join a game"), leading: HeaderSquareButton(kind: .close, identifier: "codeEntry.close", action: onClose))
            Text("Type the 4-digit code from the host's screen.")
                .font(.llBody)
                .fixedSize(horizontal: false, vertical: true)
            // 4 boxes over one hidden number field (number pad). Tapping the boxes focuses the field.
            ZStack {
                TextField("Room code", text: Binding(get: { state.joinCode }, set: actions.onJoinCodeChange))
                    .keyboardType(.numberPad)
                    .textContentType(.oneTimeCode)
                    .focused($focused)
                    .opacity(0.02)
                    .accessibilityIdentifier("codeEntry.code")
                HStack(spacing: Theme.Spacing.m) {
                    ForEach(0..<4, id: \.self) { index in
                        digitBox(index)
                    }
                }
                .contentShape(.rect)
                .onTapGesture { focused = true }
                .accessibilityHidden(true)
            }
            .frame(maxWidth: .infinity)
            if let error = state.errorText {
                Chip(text: error, fill: Theme.Palette.health)
                    .accessibilityIdentifier("codeEntry.error")
            }
            Button(state.busyText ?? "Join", action: actions.onJoin)
                .buttonStyle(.main)
                .disabled(!state.canJoin)
                .accessibilityIdentifier("codeEntry.join")
            Spacer(minLength: 0)
        }
        .foregroundStyle(Theme.Palette.ink)
        .padding(.horizontal, Theme.Spacing.margin)
        .padding(.top, Theme.Spacing.m)
        .paperBackground()
        .onAppear { focused = true }
    }
}

extension RoomCodeEntryView {
    fileprivate func digitBox(_ index: Int) -> some View {
        let digits = Array(state.joinCode)
        let digit = index < digits.count ? String(digits[index]) : ""
        let isNext = index == digits.count && focused
        return Text(digit)
            .font(.llHero)
            .monospacedDigit()
            .frame(width: 60, height: 72)
            .inkSurface(.buttonThird, fill: isNext ? Theme.Palette.paper : Theme.Palette.surface, lineWidth: isNext ? Theme.outline : Theme.chipOutline)
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Code · light") { RoomCodeEntryView(state: RoomFlowFixtures.entry(joinCode: "4242")) }
#Preview("Code · dark") { RoomCodeEntryView(state: RoomFlowFixtures.entry(joinCode: "42")).previewDark() }
#Preview("Code · AX3") { RoomCodeEntryView(state: RoomFlowFixtures.entryError).previewLargeType() }
