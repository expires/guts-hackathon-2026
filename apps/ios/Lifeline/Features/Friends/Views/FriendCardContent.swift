import Charts
import SwiftUI

/// Green when going well, orange for fine, pink for worth a look. Always paired with words.
func friendScoreColor(_ score: Int) -> Color {
    switch score {
    case 70...: Theme.Palette.money
    case 40..<70: Theme.Palette.home
    default: Theme.Palette.health
    }
}

private let mixPalette: [Color] = [
    Theme.Palette.work, Theme.Palette.money, Theme.Palette.home, Theme.Palette.family, Theme.Palette.health,
]

/// One person's card as friends see it: overall score, habit factors, and the mix when shared.
/// Used by the friend detail sheet and by the "What friends see" preview.
struct FriendCardContent: View {
    let detail: FriendDetailState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        overall
        factorsCard
        mixCard
    }

    private var overall: some View {
        InkCard(shape: .hero, hero: true, padding: Theme.Spacing.xl) {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                Text("Money habits score").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.s) {
                    Text(detail.scoreText).font(.llHero).accessibilityHidden(true)
                    Text("out of 100").font(.llLabel).foregroundStyle(Theme.Palette.muted)
                    Spacer(minLength: 0)
                    if let band = detail.bandText, let score = detail.score {
                        Chip(text: band, fill: friendScoreColor(score))
                    }
                }
                if let growth = detail.growthText {
                    Text(growth).font(.llBodyBold)
                }
                if detail.isSample { SampleBadge() }
            }
        }
        .padding(.trailing, Theme.heroShadow.width)
        .padding(.bottom, Theme.heroShadow.height)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(detail.isMe ? "Your" : "\(detail.name)'s") money habits score")
        .accessibilityValue(detail.score.map { "\($0) out of 100" } ?? "Not available")
        .accessibilityIdentifier("friend.overall")
    }

    private var factorsCard: some View {
        InkCard(shape: .cardAlt) {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                ChartHeader(title: "Their habits", help: ChartHelpCatalogue.friendFactors)
                if detail.factors.isEmpty {
                    Text("No habit scores yet. They appear once there is enough history.")
                        .font(.llBody).foregroundStyle(Theme.Palette.muted)
                } else {
                    ForEach(detail.factors) { factor in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(factor.label).font(.llBodyBold)
                                Spacer(minLength: Theme.Spacing.s)
                                Text("\(factor.score)").font(.llBodyBold.monospacedDigit())
                            }
                            InkProgressBar(
                                value: Double(factor.score) / 100, color: friendScoreColor(factor.score), height: 14
                            )
                            .animation(Motion.standard(reduceMotion: reduceMotion), value: factor.score)
                            .accessibilityHidden(true)
                        }
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(factor.label)
                        .accessibilityValue("\(factor.scoreText), \(factor.bandText)")
                        .accessibilityIdentifier("friend.factor.\(factor.id)")
                    }
                }
                ChartCaption(help: ChartHelpCatalogue.friendFactors)
            }
        }
        .accessibilityIdentifier("friend.factors")
    }

    private var mixCard: some View {
        InkCard {
            VStack(alignment: .leading, spacing: Theme.Spacing.m) {
                ChartHeader(title: "Investment mix", help: ChartHelpCatalogue.friendMix)
                if let note = detail.mixNote {
                    Text(note).font(.llBody).foregroundStyle(Theme.Palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("friend.mixNote")
                } else {
                    Chart(Array(detail.slices.enumerated()), id: \.element.id) { offset, slice in
                        SectorMark(angle: .value("Share", slice.percent), innerRadius: .ratio(0.6), angularInset: 2)
                            .foregroundStyle(mixPalette[offset % mixPalette.count])
                    }
                    .frame(height: 170)
                    .accessibilityLabel("Investment mix")
                    .accessibilityValue(detail.slices.map { "\($0.label) \($0.percentText)" }.joined(separator: ", "))
                    ForEach(Array(detail.slices.enumerated()), id: \.element.id) { offset, slice in
                        HStack(spacing: Theme.Spacing.s) {
                            RoundedRectangle(cornerRadius: 3)
                                .fill(mixPalette[offset % mixPalette.count])
                                .strokeBorder(Theme.Palette.ink, lineWidth: 2)
                                .frame(width: 10, height: 10)
                                .accessibilityHidden(true)
                            Text(slice.label).font(.llBody)
                            Spacer()
                            Text("\(Int(slice.percent.rounded()))%").font(.llBodyBold.monospacedDigit())
                        }
                        .frame(minHeight: 28)
                        .accessibilityElement(children: .combine)
                    }
                }
                ChartCaption(help: ChartHelpCatalogue.friendMix)
            }
        }
        .accessibilityIdentifier("friend.mix")
    }
}

/// "Sample data" label on any card that is not from a real connected account.
struct SampleBadge: View {
    var body: some View {
        Text("Sample data")
            .font(.llLabelBold)
            .foregroundStyle(Theme.Palette.ink)
            .padding(.horizontal, 10)
            .padding(.vertical, 3)
            .inkSurface(.badge, lineWidth: Theme.chipOutline)
            .accessibilityLabel("Sample data. Not from a real account.")
            .accessibilityIdentifier("friend.sampleBadge")
    }
}
