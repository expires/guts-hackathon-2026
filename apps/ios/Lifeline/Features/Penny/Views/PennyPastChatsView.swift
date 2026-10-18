import SwiftUI

/// Past chats (PENNY_V3_BUILD D3): Penny's earlier threads on their own screen, opened from the chat header.
/// Tap a thread to open it in the chat. Plain values only (ADR 0011).
struct PennyPastChatsView: View {
    let threads: [PennyViewState.ThreadSummary]
    var onOpen: @MainActor (String) -> Void = { _ in }
    var onClose: @MainActor () -> Void = {}

    var body: some View {
        VStack(spacing: 0) {
            ScreenHeader(title: L10n.tr("Past chats")) {
                HeaderSquareButton(kind: .close, identifier: "penny.pastChats.close", action: { onClose() })
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.l)
            .padding(.bottom, Theme.Spacing.m)
            ScrollView {
                if threads.isEmpty {
                    Text("No past chats yet. Your chats with Penny show here.")
                        .font(.llBody)
                        .foregroundStyle(Theme.Palette.muted)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, Theme.Spacing.margin)
                        .accessibilityIdentifier("penny.pastChats.empty")
                } else {
                    VStack(spacing: 0) {
                        ForEach(Array(threads.enumerated()), id: \.element.id) { index, thread in
                            if index > 0 { RuleDivider() }
                            Button { onOpen(thread.id) } label: {
                                ListRow(icon: .why, title: thread.title, subtitle: thread.detail)
                            }
                            .buttonStyle(.plain)
                            .accessibilityHint(L10n.tr("Opens this chat"))
                            .accessibilityIdentifier("penny.past.\(thread.id)")
                        }
                    }
                    .padding(.horizontal, Theme.Spacing.l)
                    .inkSurface(.card)
                    .padding(.horizontal, Theme.Spacing.margin)
                    .padding(.bottom, Theme.Spacing.l)
                }
            }
        }
        .foregroundStyle(Theme.Palette.ink)
        .background(Theme.Palette.paper)
        // A container id would replace the ids of the rows and the close button.
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("penny.pastChats")
    }
}

#Preview("Past chats · light") { PennyPastChatsView(threads: PennyFixtures.pastThreadRows) }
#Preview("Past chats · dark") { PennyPastChatsView(threads: PennyFixtures.pastThreadRows).previewDark() }
#Preview("Past chats · AX3") { PennyPastChatsView(threads: PennyFixtures.pastThreadRows).previewLargeType() }
#Preview("Past chats · empty") { PennyPastChatsView(threads: []) }
