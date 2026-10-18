import SwiftUI

/// App UI language (ADR 0063). Stored in UserDefaults `penny.language`.
///
/// - Views: `@Environment(\.appLanguage)`. RootScreen also sets `\.locale`, so `Text("literal")` switches live.
/// - ViewModels and other code that builds `String` values: `L10n.tr("Text")`.
/// - Penny: `LiveClient` sends `ChatRequest.language` when the caller leaves it empty.
/// - Change it with `AppLanguage.set(_:)` or `@AppStorage(AppLanguage.storageKey)`. The UI updates at once.
enum AppLanguage: String, CaseIterable, Identifiable, Sendable {
    case en
    case fr
    case es
    case pt
    case it
    case zhHans = "zh-Hans"
    case hi
    case ne

    static let storageKey = "penny.language"

    var id: String { rawValue }

    /// The language's own name, shown in the picker.
    var nativeName: String {
        switch self {
        case .en: "English"
        case .fr: "Français"
        case .es: "Español"
        case .pt: "Português"
        case .it: "Italiano"
        case .zhHans: "简体中文"
        case .hi: "हिन्दी"
        case .ne: "नेपाली"
        }
    }

    /// English name, for VoiceOver hints and logs.
    var englishName: String {
        switch self {
        case .en: "English"
        case .fr: "French"
        case .es: "Spanish"
        case .pt: "Portuguese"
        case .it: "Italian"
        case .zhHans: "Simplified Chinese"
        case .hi: "Hindi"
        case .ne: "Nepali"
        }
    }

    /// Locale for SwiftUI lookups and formatting. Western digits always (ADR 0063), also for Hindi and Nepali.
    var locale: Locale {
        switch self {
        case .hi, .ne: Locale(identifier: rawValue + "@numbers=latn")
        default: Locale(identifier: rawValue)
        }
    }

    /// The compiled String Catalog table for this language (`<code>.lproj`). Main bundle when it has none yet.
    var bundle: Bundle {
        guard let path = Bundle.main.path(forResource: rawValue, ofType: "lproj"),
              let bundle = Bundle(path: path) else { return .main }
        return bundle
    }

    /// The saved choice, else the first supported device language, else English.
    static var current: AppLanguage {
        if let raw = UserDefaults.standard.string(forKey: storageKey), let saved = AppLanguage(rawValue: raw) {
            return saved
        }
        return deviceDefault
    }

    /// First device language the app supports, else English.
    static var deviceDefault: AppLanguage {
        for identifier in Locale.preferredLanguages {
            if identifier.hasPrefix("zh-Hans") || identifier == "zh-CN" || identifier.hasPrefix("zh-SG") { return .zhHans }
            let code = String(identifier.prefix { $0 != "-" && $0 != "_" })
            if code != "zh", let match = AppLanguage(rawValue: code) { return match }
        }
        return .en
    }

    /// Saves the choice. Views that read `@AppStorage(AppLanguage.storageKey)` (RootScreen) update at once.
    static func set(_ language: AppLanguage) {
        UserDefaults.standard.set(language.rawValue, forKey: storageKey)
    }

    /// Languages planned but not built. The picker shows them disabled with "Coming soon".
    static let comingSoon: [ComingSoonLanguage] = [
        .init(code: "ar", nativeName: "العربية", englishName: "Arabic"),
        .init(code: "ur", nativeName: "اردو", englishName: "Urdu"),
        .init(code: "bn", nativeName: "বাংলা", englishName: "Bengali"),
        .init(code: "pl", nativeName: "Polski", englishName: "Polish"),
        .init(code: "tr", nativeName: "Türkçe", englishName: "Turkish"),
    ]
}

/// A language shown disabled in the picker.
struct ComingSoonLanguage: Identifiable, Hashable, Sendable {
    let code: String
    let nativeName: String
    let englishName: String
    var id: String { code }
}

extension EnvironmentValues {
    /// The app UI language. Set by RootScreen from `@AppStorage(AppLanguage.storageKey)`.
    @Entry var appLanguage: AppLanguage = .en
}

/// Localised strings for code outside a SwiftUI `Text` literal (ViewModels, alerts, accessibility text).
///
///     state.title = L10n.tr("Your next move")
///     state.subtitle = L10n.tr("\(count) bills this month")
///
/// The literal is the String Catalog key (English source), so the build extracts it into
/// `Resources/Localizable.xcstrings`. Lookup uses `AppLanguage.current`, so a change applies the next time
/// the ViewModel builds its state (RootScreen bumps `appDataVersion` on a language change).
enum L10n {
    static let interpolationLocale = Locale(identifier: "en_US_POSIX")

    static func tr(_ key: String.LocalizationValue, comment: StaticString? = nil) -> String {
        tr(key, language: .current, comment: comment)
    }

    static func tr(_ key: String.LocalizationValue, language: AppLanguage, comment: StaticString? = nil) -> String {
        // Lookup uses the language's .lproj bundle. Interpolated numbers use POSIX formatting: Western digits and
        // no grouping, exactly like plain "\(n)" interpolation, so years stay "2021" (not "2,021" or "2 021").
        // Format money and large counts before interpolating (Money.format, LLAmount).
        String(localized: key, table: nil, bundle: language.bundle, locale: Self.interpolationLocale, comment: comment)
    }
}
