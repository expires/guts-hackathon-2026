import SwiftUI

/// One 0 to 100 stat with a label and a bar.
struct StatBar: View {
    let stat: StatState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
            HStack {
                Label(stat.kind.title, systemImage: Theme.systemImage(for: stat.kind))
                    .font(.subheadline.weight(.medium))
                Spacer()
                Text("\(stat.value)")
                    .font(.subheadline.monospacedDigit())
                    .contentTransition(.numericText(value: Double(stat.value)))
            }
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule().fill(.quaternary)
                    Capsule()
                        .fill(Theme.color(for: stat.kind).gradient)
                        .frame(width: proxy.size.width * CGFloat(min(100, max(0, stat.value))) / 100)
                }
            }
            .frame(height: 8)
            .animation(Motion.standard(reduceMotion: reduceMotion), value: stat.value)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(stat.kind.title)
        .accessibilityValue("\(stat.value) out of 100")
        .accessibilityIdentifier("stat.\(stat.kind.rawValue)")
    }
}

/// Shows where a number came from and how fresh it is: live, saved copy or sample.
struct SourceChip: View {
    let source: SourceChipState

    var body: some View {
        HStack(spacing: Theme.Spacing.xs) {
            Circle()
                .fill(Theme.color(for: source.status))
                .frame(width: 8, height: 8)
            Text(source.name)
                .font(.caption.weight(.semibold))
            Text(source.status.label)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, Theme.Spacing.m)
        .frame(minHeight: 32)
        .glassEffect(.regular, in: .capsule)
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
                .font(.footnote.weight(.semibold))
                .foregroundStyle(.secondary)
            FlowRow(spacing: Theme.Spacing.s) {
                ForEach(sources) { SourceChip(source: $0) }
            }
            ForEach(notes, id: \.self) { note in
                Label(note, systemImage: "info.circle")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .accessibilityIdentifier("sourceNote")
            }
        }
    }
}

/// Label shown on every screen that uses canned data.
struct DemoDataBadge: View {
    var body: some View {
        Label("Sample data", systemImage: "testtube.2")
            .font(.caption.weight(.semibold))
            .padding(.horizontal, Theme.Spacing.m)
            .padding(.vertical, Theme.Spacing.xs)
            .glassEffect(.regular.tint(.orange.opacity(0.3)), in: .capsule)
            .accessibilityLabel("Sample data. Not from the live server.")
            .accessibilityIdentifier("demoDataBadge")
    }
}

/// "Demo payment" label for every paid screen.
struct DemoPaymentLabel: View {
    var body: some View {
        Label(Brand.demoPaymentLabel, systemImage: "creditcard.trianglebadge.exclamationmark")
            .font(.caption.weight(.semibold))
            .padding(.horizontal, Theme.Spacing.m)
            .padding(.vertical, Theme.Spacing.xs)
            .glassEffect(.regular.tint(.purple.opacity(0.25)), in: .capsule)
            .accessibilityLabel("Demo payment. No real money is taken.")
            .accessibilityIdentifier("demoPaymentLabel")
    }
}

/// Large primary action with a minimum height of 56 pt.
struct PrimaryButton: View {
    let title: String
    var systemImage: String?
    var isBusy = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Theme.Spacing.s) {
                if isBusy {
                    ProgressView()
                } else if let systemImage {
                    Image(systemName: systemImage)
                }
                Text(title)
            }
            .font(.title3.bold())
            .frame(maxWidth: .infinity, minHeight: 56)
        }
        .buttonStyle(.glassProminent)
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
