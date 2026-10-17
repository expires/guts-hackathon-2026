import SwiftUI

// One reusable way to explain a chart: a one-line caption under it and a (?) button in its header
// that opens a short sheet. All wording lives in `ChartHelp` so it can be reviewed in one place.

/// The words for one chart. Describe, never recommend. Scenario charts keep the "not a forecast" wording.
struct ChartHelp: Identifiable, Hashable, Sendable {
    let id: String
    /// Sheet title, also the chart name read by VoiceOver.
    let title: String
    /// One line under the chart: how to read it.
    let caption: String
    let whatItShows: String
    let howToRead: String
    let whatItMeansForYou: String
}

/// The catalogue of chart explanations. Add new charts here.
enum ChartHelpCatalogue {
    static let netWorth = ChartHelp(
        id: "netWorth",
        title: "Net worth",
        caption: "The small line on Net worth shows how your total has moved lately.",
        whatItShows: "Net worth is what you own minus what you owe. The small line next to it is a tiny history of that total.",
        howToRead: "The left end is the earliest point and the right end is today. A line that climbs means the total went up. A line that dips means it went down.",
        whatItMeansForYou: "It is a quick sense of direction for your whole picture. One quiet week or one big bill can move it a little."
    )

    static let nextMoveConfidence = ChartHelp(
        id: "nextMoveConfidence",
        title: "How sure we are",
        caption: "More filled bars means stronger evidence behind this move.",
        whatItShows: "The meter shows how much evidence sits behind the suggested move, based on how well your numbers and past data back it up.",
        howToRead: "Read the word above the meter first. A full meter means the evidence is strong. A short meter means we are less sure and the number could change.",
        whatItMeansForYou: "A lower meter does not mean the move is wrong. It means the yearly amount is a rough estimate."
    )

    static let monthSummary = ChartHelp(
        id: "monthSummary",
        title: "Earned and spent",
        caption: "The bar is the share of what you earned that went out this month.",
        whatItShows: "Two totals for the month: money that came in and money that went out. The bar puts them side by side.",
        howToRead: "A short bar means you spent a small part of what came in. A bar that fills up means most of it went out.",
        whatItMeansForYou: "It shows the balance between earning and spending for this month only. One month can be unusual."
    )

    static let moneyInAndOut = ChartHelp(
        id: "moneyInAndOut",
        title: "Money in and out",
        caption: "Each pair of bars is a month: green is money in, orange is money out.",
        whatItShows: "How much came into your accounts and how much left them, month by month, for the period you picked.",
        howToRead: "Compare the two bars in each pair. Green taller than orange means more came in than went out that month. Orange taller means the other way round.",
        whatItMeansForYou: "It shows whether your months tend to end ahead or behind, and which months stand out."
    )

    static let spendingByCategory = ChartHelp(
        id: "spendingByCategory",
        title: "Where your money goes",
        caption: "The long bar splits your spending by kind. A wider colour means a bigger share. The small lines show each kind over time.",
        whatItShows: "Your spending split into kinds, like food, bills and travel, with each kind's share of the total.",
        howToRead: "Each coloured block in the bar matches a row below. Wider blocks are bigger shares. The tag on a row compares it with the same number of months before.",
        whatItMeansForYou: "It shows which kinds of spending take the most. Shares add up to everything you spent in the period."
    )

    static let spendingPatterns = ChartHelp(
        id: "spendingPatterns",
        title: "Spending patterns",
        caption: "Each bar is a day of the week. The orange bar is the day you spend most.",
        whatItShows: "How your spending is spread across the days of the week, and how much falls on weekends compared with weekdays.",
        howToRead: "Taller bars are days with more spending, added up over the period. The split bar above shows weekdays on the left and weekends on the right.",
        whatItMeansForYou: "It shows when your spending tends to happen. It describes the past and does not predict the future."
    )

    static let subscriptions = ChartHelp(
        id: "subscriptions",
        title: "Subscriptions",
        caption: "Regular payments we spotted, with what they cost a month and a year.",
        whatItShows: "Payments that repeat at a steady amount and rhythm, like streaming or phone plans, found in your transactions.",
        howToRead: "The big numbers add up every subscription we found. Each row shows one, with its yearly cost underneath.",
        whatItMeansForYou: "It can miss a payment or count one that is not really a subscription. It is a list to look over, not a verdict."
    )

    static let investmentSplit = ChartHelp(
        id: "investmentSplit",
        title: "What it is made of",
        caption: "Each slice of the ring is a share of what you hold. Bigger slice, bigger share.",
        whatItShows: "How the money in your investments is divided between different kinds of holdings.",
        howToRead: "Match each colour to the list below the ring. The percentages add up to 100.",
        whatItMeansForYou: "It shows how spread out your investments are. If one slice is very big, that part drives most of the ups and downs."
    )

    static let isaReplay = ChartHelp(
        id: "isaReplay",
        title: "Replay your ISA",
        caption: "Each line starts at 100. If a line ends at 150, that mix grew by half.",
        whatItShows: "How different mixes of investments would have done if you had put money in at the start of a real stretch of the past.",
        howToRead: "Every line starts at 100 on the left. Higher means that mix was worth more at that point. Dips show the rough patches along the way.",
        whatItMeansForYou: "It shows how each mix behaved in one past period. The numbers are made-up, shaped like real markets, and are not a forecast."
    )

    static let replayNumbers = ChartHelp(
        id: "replayNumbers",
        title: "Replay numbers",
        caption: "Biggest drop is the worst fall from a high point. Yearly growth is the average pace.",
        whatItShows: "Three numbers for each mix: the biggest drop, how long it took to get back to the starting value, and the average growth per year.",
        howToRead: "A bigger drop means a bumpier ride. A longer time to get back means the low point lasted longer. Yearly growth smooths the whole period into one pace.",
        whatItMeansForYou: "Together they describe how smooth or rough each mix was in this past period. They do not say how it will go next time."
    )

    static let possiblePaths = ChartHelp(
        id: "possiblePaths",
        title: "Possible paths",
        caption: "The shaded band shows the middle 8 in 10 outcomes from similar past periods; the line is the middle one.",
        whatItShows: "A spread of ways your money could have grown, built from similar stretches of the past. It is not a forecast.",
        howToRead: "The line is the middle outcome. The shaded band covers 8 in 10 of the outcomes. The top and bottom edges are the best and worst of that group, and some paths fall outside the band.",
        whatItMeansForYou: "A wide band means results varied a lot in the past. The real future can land anywhere, including outside the band."
    )

    static let habitsScore = ChartHelp(
        id: "habitsScore",
        title: "Money habits score",
        caption: "The ring fills up to your score out of 100. More ring means stronger habits.",
        whatItShows: "One score out of 100 that combines how you save, spend and handle bills over the recent period.",
        howToRead: "The coloured part of the ring is your score. Green is going well, orange is fine, pink is worth a look. The factors below show what makes it up.",
        whatItMeansForYou: "It is a summary of the recent past, not a grade of you. It moves as your habits and your data change."
    )

    static let habitFactors = ChartHelp(
        id: "habitFactors",
        title: "Habit factors",
        caption: "Each bar is one habit scored out of 100. A fuller bar means a stronger habit.",
        whatItShows: "The separate parts that make up your overall score, each with its own score and a short reason.",
        howToRead: "Read the plain-English line first, then the bar. The colour matches the ring: green, orange or pink. A factor with no bar did not have enough data.",
        whatItMeansForYou: "It shows which habits lift your score and which hold it back, based on the data we could see."
    )
}

/// One line under a chart: how to read it. Selectable by VoiceOver like any text.
struct ChartCaption: View {
    let help: ChartHelp

    var body: some View {
        Text(help.caption)
            .font(.llLabel)
            .foregroundStyle(Theme.Palette.muted)
            .multilineTextAlignment(.leading)
            .fixedSize(horizontal: false, vertical: true)
            .frame(maxWidth: .infinity, alignment: .leading)
            .accessibilityIdentifier("chart.caption.\(help.id)")
    }
}

/// The (?) button for a chart header. Opens the explainer sheet.
struct ChartInfoButton: View {
    let help: ChartHelp
    @State private var isShowing = false

    var body: some View {
        Button { isShowing = true } label: {
            LLIconImage(.why, size: 28)
                .foregroundStyle(Theme.Palette.ink)
                .frame(width: Theme.minTarget, height: Theme.minTarget)
                .contentShape(.rect)
        }
        .buttonStyle(.plain)
        .accessibilityLabel("About this chart")
        .accessibilityHint(help.title)
        .accessibilityIdentifier("chart.info.\(help.id)")
        .llSheet(isPresented: $isShowing) {
            ChartExplainerSheet(help: help) { isShowing = false }
        }
    }
}

/// A header row: title on the left, (?) on the right. For charts whose header is plain text.
struct ChartHeader: View {
    let title: String
    let help: ChartHelp

    var body: some View {
        HStack(spacing: Theme.Spacing.s) {
            Text(title).font(.llBodyBold).accessibilityAddTraits(.isHeader)
            Spacer(minLength: 0)
            ChartInfoButton(help: help)
        }
    }
}

/// Caption with the (?) at its end, for charts that have no header of their own (tiles, meters).
struct ChartCaptionRow: View {
    let help: ChartHelp

    var body: some View {
        HStack(alignment: .center, spacing: Theme.Spacing.xs) {
            ChartCaption(help: help)
            ChartInfoButton(help: help)
        }
    }
}

/// The sheet: What this shows, How to read it, What it means for you.
struct ChartExplainerSheet: View {
    let help: ChartHelp
    let onClose: () -> Void

    var body: some View {
        SheetContainer(title: help.title, closeIdentifier: "chart.explainer.close", onClose: onClose) {
            section("What this shows", help.whatItShows, id: "shows")
            section("How to read it", help.howToRead, id: "read")
            section("What it means for you", help.whatItMeansForYou, id: "means")
        }
        .accessibilityIdentifier("chart.explainer.\(help.id)")
    }

    private func section(_ title: String, _ text: String, id: String) -> some View {
        InkCard(shape: id == "read" ? .cardAlt : .card) {
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                Text(title).font(.llBodyBold).accessibilityAddTraits(.isHeader)
                Text(text).font(.llBody).fixedSize(horizontal: false, vertical: true)
            }
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Previews

#Preview("Sheet · light") {
    LLSheetFrame { ChartExplainerSheet(help: ChartHelpCatalogue.possiblePaths) {} }
}

#Preview("Sheet · dark") {
    LLSheetFrame { ChartExplainerSheet(help: ChartHelpCatalogue.isaReplay) {} }.previewDark()
}

#Preview("Sheet · AX3") {
    LLSheetFrame { ChartExplainerSheet(help: ChartHelpCatalogue.moneyInAndOut) {} }.previewLargeType()
}

#Preview("Header and caption · light") {
    InkCard {
        VStack(alignment: .leading, spacing: Theme.Spacing.m) {
            ChartHeader(title: "Money in and out", help: ChartHelpCatalogue.moneyInAndOut)
            RoundedRectangle(cornerRadius: 8).fill(Theme.Palette.rule).frame(height: 120)
            ChartCaption(help: ChartHelpCatalogue.moneyInAndOut)
        }
    }
    .padding(20)
    .paperBackground()
}

#Preview("Caption row · AX3") {
    ChartCaptionRow(help: ChartHelpCatalogue.nextMoveConfidence).padding(20).paperBackground().previewLargeType()
}
