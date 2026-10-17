import SwiftUI

/// Friends tab: the leaderboard, a way to add friends and a way to see what they see.
struct FriendsView: View {
    let state: FriendsViewState
    var actions: FriendsActions = .noop
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var pendingRemoval: FriendsViewState.Row?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: "Friends") {
                    if state.isSampleData && !state.phase.isLoading { SampleBadge() }
                }
                Text("Compare money habits with friends. They only ever see scores, never your amounts.")
                    .font(.llBody)
                    .foregroundStyle(Theme.Palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("friends.intro")
                switch state.phase {
                case let .loading(loading):
                    LoadingStateView(state: loading)
                case let .failed(error):
                    ErrorStateView(state: error, onRetry: actions.onRetry)
                case .ready:
                    buttons
                    if state.friendCount == 0 { emptyState } else { leaderboard }
                }
            }
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: state.rows)
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
        .overlay(alignment: .top) { toast }
        .confirmationDialog(
            "Remove \(pendingRemoval?.name ?? "this friend")?",
            isPresented: Binding(get: { pendingRemoval != nil }, set: { if !$0 { pendingRemoval = nil } }),
            titleVisibility: .visible,
            presenting: pendingRemoval
        ) { row in
            Button("Remove", role: .destructive) { actions.onRemove(row.id) }
            Button("Keep", role: .cancel) {}
        } message: { _ in
            Text("You will both stop seeing each other.")
        }
    }

    private var buttons: some View {
        HStack(spacing: Theme.Spacing.s) {
            Button("Add a friend", icon: .family, action: actions.onOpenAdd)
                .buttonStyle(.main)
                .accessibilityIdentifier("friends.add")
            Button("What friends see", action: actions.onOpenMine)
                .buttonStyle(.second)
                .accessibilityIdentifier("friends.mine")
        }
    }

    // MARK: Leaderboard

    private var leaderboard: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                ChartHeader(title: "Money habits score", help: ChartHelpCatalogue.friendsLeaderboard)
                ChartCaption(help: ChartHelpCatalogue.friendsLeaderboard)
            }
            ForEach(state.rows) { row in
                Button { actions.onSelect(row.id) } label: { RowCard(row: row) }
                    .buttonStyle(.plain)
                    .contextMenu {
                        if !row.isMe {
                            Button("Remove friend", role: .destructive) { pendingRemoval = row }
                        }
                    }
                    .accessibilityAction(named: "Remove friend") { if !row.isMe { pendingRemoval = row } }
            }
            if state.hasGrowth {
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    ChartHeader(title: "Growth index", help: ChartHelpCatalogue.growthIndex)
                    ChartCaption(help: ChartHelpCatalogue.growthIndex)
                }
                .padding(.top, Theme.Spacing.s)
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("friends.leaderboard")
    }

    private var emptyState: some View {
        InkCard(shape: .cardAlt) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                Text("No friends yet").font(.llBodyBold).accessibilityAddTraits(.isHeader)
                Text("Add a friend with their code, or share yours. Once they join, you both appear here.")
                    .font(.llBody)
                    .foregroundStyle(Theme.Palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
                Button("Add a friend", icon: .family, action: actions.onOpenAdd)
                    .buttonStyle(.main)
                    .accessibilityIdentifier("friends.empty.add")
            }
        }
        .accessibilityIdentifier("friends.empty")
    }

    // MARK: Toast

    @ViewBuilder
    private var toast: some View {
        if let banner = state.banner {
            HStack(spacing: Theme.Spacing.s) {
                LLIconImage(banner.kind == .success ? .check : .why, size: 24)
                Text(banner.text).font(.llBodyBold).fixedSize(horizontal: false, vertical: true)
            }
            .foregroundStyle(Theme.Palette.onArea)
            .padding(.horizontal, Theme.Spacing.l)
            .padding(.vertical, Theme.Spacing.m)
            .inkSurface(
                .buttonAlt, fill: banner.kind == .success ? Theme.Palette.money : Theme.Palette.health
            )
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .transition(.move(edge: .top).combined(with: .opacity))
            .accessibilityElement(children: .combine)
            .accessibilityAddTraits(.updatesFrequently)
            .accessibilityIdentifier("friends.toast")
            .task(id: banner) {
                try? await Task.sleep(for: .seconds(4))
                if !Task.isCancelled { actions.onDismissBanner() }
            }
            .onTapGesture { actions.onDismissBanner() }
        }
    }
}

// MARK: - Row

private struct RowCard: View {
    let row: FriendsViewState.Row
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        let onTint = row.isMe
        InkCard(fill: onTint ? Theme.Palette.work : Theme.Palette.surface) {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.m) {
                    Text("\(row.rank)")
                        .font(.llTitle.monospacedDigit())
                        .frame(minWidth: 28, alignment: .leading)
                    Text(row.name).font(.llBodyBold).lineLimit(1)
                    Spacer(minLength: Theme.Spacing.s)
                    Text(row.scoreText).font(.llTitle.monospacedDigit())
                    Chevron()
                }
                InkProgressBar(
                    value: Double(row.score ?? 0) / 100, color: row.score.map(friendScoreColor) ?? Theme.Palette.other,
                    height: 14
                )
                .animation(Motion.standard(reduceMotion: reduceMotion), value: row.score)
                if let compare = row.compareText {
                    Text(compare).font(.llLabelBold)
                }
                if let growth = row.growthText {
                    Text(growth).font(.llLabel)
                }
                if row.isSample { SampleBadge() }
            }
            .foregroundStyle(onTint ? Theme.Palette.onArea : Theme.Palette.ink)
            .frame(minHeight: Theme.minTarget)
        }
        .contentShape(.rect)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(row.spokenText)
        .accessibilityHint("Opens their habits")
        .accessibilityIdentifier("friends.row.\(row.id)")
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Loaded · light") { NavigationStack { FriendsView(state: Fixtures.Friends.loaded) } }
#Preview("Loaded · dark") { NavigationStack { FriendsView(state: Fixtures.Friends.loaded) }.previewDark() }
#Preview("Loaded · AX3") { NavigationStack { FriendsView(state: Fixtures.Friends.loaded) }.previewLargeType() }
#Preview("Added toast · light") { NavigationStack { FriendsView(state: Fixtures.Friends.added) } }
#Preview("Empty · light") { NavigationStack { FriendsView(state: Fixtures.Friends.empty) } }
#Preview("Empty · dark") { NavigationStack { FriendsView(state: Fixtures.Friends.empty) }.previewDark() }
#Preview("Loading · light") { NavigationStack { FriendsView(state: Fixtures.Friends.loading) } }
#Preview("Error · light") { NavigationStack { FriendsView(state: Fixtures.Friends.error) } }
