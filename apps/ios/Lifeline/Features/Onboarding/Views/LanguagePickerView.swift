import SwiftUI

/// Pick the app language (ADR 0063): the 8 languages in their own names, then "Coming soon" ones.
/// The screen's text redraws in the picked language at once; Confirm applies it.
struct LanguagePickerView: View {
    let selection: AppLanguage
    var onPick: (AppLanguage) -> Void = { _ in }
    var onConfirm: () -> Void = {}
    /// Nil hides the back button.
    var onBack: (() -> Void)?
    /// Onboarding only (ADR 0069): Skip keeps the current language. Nil hides it.
    var onSkip: (() -> Void)?

    var body: some View {
        let texts = LanguageScreenTexts.texts(for: selection)
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(
                    title: texts.title,
                    leading: onBack.map { back in HeaderSquareButton(kind: .back, identifier: "onboarding.back", action: back) }
                ) {
                    if let onSkip {
                        Button("Skip", action: onSkip)
                            .buttonStyle(.text)
                            .frame(minWidth: Theme.minTarget, minHeight: Theme.minTarget)
                            .contentShape(.rect)
                            .accessibilityIdentifier("onboarding.skip")
                    }
                }
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    Text(verbatim: texts.studentsFact).font(.llBody).fixedSize(horizontal: false, vertical: true)
                        .accessibilityIdentifier("onboarding.language.fact")
                    Text(verbatim: LanguageScreenTexts.sourceLine).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                .padding(Theme.Spacing.l)
                .frame(maxWidth: .infinity, alignment: .leading)
                .inkSurface(.cardAlt)
                .accessibilityElement(children: .combine)
                VStack(spacing: 0) {
                    ForEach(Array(AppLanguage.allCases.enumerated()), id: \.element.id) { offset, item in
                        if offset > 0 { RuleDivider() }
                        let isOn = item == selection
                        Button { onPick(item) } label: {
                            HStack {
                                Text(verbatim: item.nativeName).font(.llBodyBold)
                                Spacer()
                                if isOn { LLIconImage(.check, size: 24) }
                            }
                            .foregroundStyle(Theme.Palette.ink)
                            .padding(.horizontal, Theme.Spacing.l)
                            .frame(maxWidth: .infinity, minHeight: Theme.minTarget + 4, alignment: .leading)
                            .contentShape(.rect)
                        }
                        .buttonStyle(.plain)
                        .accessibilityAddTraits(isOn ? .isSelected : [])
                        .accessibilityHint(item.englishName)
                        .accessibilityIdentifier("onboarding.language.\(item.rawValue)")
                    }
                }
                .inkSurface(.card)
                VStack(spacing: 0) {
                    ForEach(Array(AppLanguage.comingSoon.enumerated()), id: \.element.id) { offset, item in
                        if offset > 0 { RuleDivider() }
                        HStack {
                            Text(verbatim: item.nativeName).font(.llBody)
                            Spacer()
                            Chip(text: texts.comingSoon, fill: Theme.Palette.other)
                        }
                        .padding(.horizontal, Theme.Spacing.l)
                        .frame(minHeight: Theme.minTarget)
                        .opacity(0.7)
                        .accessibilityElement(children: .combine)
                        .accessibilityHint(item.englishName)
                    }
                }
                .inkSurface(.cardAlt)
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            Button(texts.confirm, action: onConfirm)
                .buttonStyle(.main)
                .accessibilityIdentifier("onboarding.language.confirm")
                .padding(.horizontal, Theme.Spacing.margin)
                .padding(.vertical, Theme.Spacing.m)
                .background(Theme.Palette.paper.ignoresSafeArea(edges: .bottom))
        }
        // Catalog strings on this screen also follow the picked language at once.
        .environment(\.locale, selection.locale)
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }
}

/// Standalone language screen (You > Change language). Confirm saves the app language, then `onDone`.
struct LanguageScreen: View {
    let onDone: @MainActor () -> Void
    @State private var selection = AppLanguage.current

    init(onDone: @escaping @MainActor () -> Void) {
        self.onDone = onDone
    }

    var body: some View {
        LanguagePickerView(
            selection: selection,
            onPick: { selection = $0 },
            onConfirm: {
                AppLanguage.set(selection)
                onDone()
            },
            onBack: { onDone() }
        )
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("English · light") { LanguagePickerView(selection: .en) }
#Preview("Français · dark") { LanguagePickerView(selection: .fr).previewDark() }
#Preview("नेपाली · AX3") { LanguagePickerView(selection: .ne).previewLargeType() }
