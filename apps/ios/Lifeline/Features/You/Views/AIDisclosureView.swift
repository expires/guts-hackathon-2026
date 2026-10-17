import SwiftUI

/// "How Penny uses AI" (ADR 0043): four sections of short points, in our own sheet.
struct AIDisclosureView: View {
    let state: AIDisclosureViewState
    var onClose: () -> Void = {}

    var body: some View {
        SheetContainer(title: state.title, closeIdentifier: "aiDisclosure.close", onClose: onClose) {
            ForEach(state.sections) { section in
                VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                    Text(section.heading)
                        .font(.llBodyBold)
                        .accessibilityAddTraits(.isHeader)
                    ForEach(section.points, id: \.self) { point in
                        HStack(alignment: .firstTextBaseline, spacing: Theme.Spacing.s) {
                            Circle().fill(Theme.Palette.ink).frame(width: 6, height: 6).accessibilityHidden(true)
                            Text(point).font(.llBody).fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                .padding(Theme.Spacing.l)
                .frame(maxWidth: .infinity, alignment: .leading)
                .inkSurface(section.id.count.isMultiple(of: 2) ? .card : .cardAlt)
                .accessibilityElement(children: .contain)
                .accessibilityIdentifier("aiDisclosure.section")
            }
        }
    }
}

#Preview("Bundled · light") { LLSheetFrame { AIDisclosureView(state: .load()) } }
#Preview("Bundled · dark") { LLSheetFrame { AIDisclosureView(state: .load()) }.previewDark() }
#Preview("Bundled · AX3") { LLSheetFrame { AIDisclosureView(state: .load()) }.previewLargeType() }
#Preview("Fallback · light") { LLSheetFrame { AIDisclosureView(state: .fallback) } }
