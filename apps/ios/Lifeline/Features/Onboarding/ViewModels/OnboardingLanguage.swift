import Foundation

/// The language screen's own words in each `AppLanguage` (ADR 0063), so the screen redraws on tap
/// even before the String Catalog has these strings. Machine-written translations (labelled in the README).
struct LanguageScreenTexts: Equatable, Sendable {
    var title: String
    var studentsFact: String
    var confirm: String
    var comingSoon: String

    /// The HESA source line is a publication title, so it stays in English.
    static let sourceLine = "HESA, Higher Education Student Statistics 2024/25"

    static func texts(for language: AppLanguage) -> LanguageScreenTexts {
        switch language {
        case .en:
            .init(
                title: "Choose your language",
                studentsFact: "About 1 in 4 students at UK universities come from outside the UK (HESA 2024/25).",
                confirm: "Confirm", comingSoon: "Coming soon"
            )
        case .fr:
            .init(
                title: "Choisissez votre langue",
                studentsFact: "Environ 1 étudiant sur 4 dans les universités britanniques vient de l'extérieur du Royaume-Uni (HESA 2024/25).",
                confirm: "Confirmer", comingSoon: "Bientôt disponible"
            )
        case .es:
            .init(
                title: "Elige tu idioma",
                studentsFact: "Alrededor de 1 de cada 4 estudiantes de las universidades del Reino Unido viene de fuera del Reino Unido (HESA 2024/25).",
                confirm: "Confirmar", comingSoon: "Próximamente"
            )
        case .pt:
            .init(
                title: "Escolha o seu idioma",
                studentsFact: "Cerca de 1 em cada 4 estudantes das universidades do Reino Unido vem de fora do Reino Unido (HESA 2024/25).",
                confirm: "Confirmar", comingSoon: "Em breve"
            )
        case .it:
            .init(
                title: "Scegli la tua lingua",
                studentsFact: "Circa 1 studente su 4 nelle università del Regno Unito viene da fuori del Regno Unito (HESA 2024/25).",
                confirm: "Conferma", comingSoon: "Prossimamente"
            )
        case .zhHans:
            .init(
                title: "选择你的语言",
                studentsFact: "英国大学中约四分之一的学生来自英国以外（HESA 2024/25）。",
                confirm: "确认", comingSoon: "即将推出"
            )
        case .hi:
            .init(
                title: "अपनी भाषा चुनें",
                studentsFact: "ब्रिटेन के विश्वविद्यालयों में लगभग 4 में से 1 छात्र ब्रिटेन के बाहर से आते हैं (HESA 2024/25)।",
                confirm: "पुष्टि करें", comingSoon: "जल्द आ रहा है"
            )
        case .ne:
            .init(
                title: "आफ्नो भाषा छान्नुहोस्",
                studentsFact: "बेलायतका विश्वविद्यालयहरूमा करिब 4 मध्ये 1 विद्यार्थी बेलायत बाहिरबाट आउँछन् (HESA 2024/25)।",
                confirm: "पुष्टि गर्नुहोस्", comingSoon: "छिट्टै आउँदैछ"
            )
        }
    }
}
