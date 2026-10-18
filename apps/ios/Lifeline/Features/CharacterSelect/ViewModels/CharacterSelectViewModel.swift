import Foundation
import Observation

@MainActor
@Observable
final class CharacterSelectViewModel {
    enum Route: Equatable {
        case form(CharacterFormMode)
        case startYear(CharacterChoice)
        case store
        case rooms
        case sources
        case debugMenu
    }

    private let session: GameSession
    private(set) var characters: CharactersResponse?
    private(set) var phase: LoadPhase = .loading(.init(message: L10n.tr("Loading characters")))
    @ObservationIgnored var onRoute: @MainActor (Route) -> Void = { _ in }

    init(session: GameSession) {
        self.session = session
    }

    var state: CharacterSelectViewState {
        Self.makeState(
            characters: characters,
            phase: phase,
            ownsGodMode: session.ownsGodMode,
            usesSampleData: session.usesSampleData
        )
    }

    var actions: CharacterSelectActions {
        CharacterSelectActions(
            onSelect: { [weak self] in self?.select($0) },
            onRetry: { [weak self] in Task { await self?.load() } },
            onOpenRooms: { [weak self] in self?.onRoute(.rooms) },
            onOpenStore: { [weak self] in self?.onRoute(.store) },
            onOpenSources: { [weak self] in self?.onRoute(.sources) },
            onVersionLongPress: { [weak self] in
                if ClientFactory.isDebugBuild { self?.onRoute(.debugMenu) }
            }
        )
    }

    func load() async {
        if characters == nil { phase = .loading(.init(message: L10n.tr("Loading characters"))) }
        do {
            // Cached first (bundled or last server copy), then fresh (ADR 0060).
            try await session.client.load(CachedOps.characters) { [weak self] characters in
                self?.characters = characters
                self?.phase = .ready
            }
        } catch {
            if characters == nil { phase = .failed(.from(APIError.map(error))) }
        }
    }

    func select(_ cardID: String) {
        switch cardID {
        case "self":
            onRoute(.form(.playYourself))
        case "god":
            // God Mode is cut (ADR 0067).
            break
        case "random":
            if let random = characters?.random {
                onRoute(.startYear(CharacterChoice(mode: .random, character: random)))
            }
        default:
            let presetID = cardID.replacingOccurrences(of: "preset.", with: "")
            if let preset = characters?.presets.first(where: { ($0.id ?? $0.name) == presetID }) {
                onRoute(.startYear(CharacterChoice(mode: .preset, character: preset)))
            }
        }
    }

    static func makeState(
        characters: CharactersResponse?,
        phase: LoadPhase,
        ownsGodMode: Bool,
        usesSampleData: Bool
    ) -> CharacterSelectViewState {
        var cards: [CharacterSelectViewState.Card] = [
            .init(
                id: "self",
                kind: .playYourself,
                emoji: "🪞",
                title: L10n.tr("Play yourself"),
                subtitle: L10n.tr("Enter your own job, pay and savings. Start here."),
                detail: nil,
                badge: "Recommended",
                isLocked: false
            ),
        ]
        for preset in characters?.presets ?? [] {
            cards.append(
                .init(
                    id: "preset.\(preset.id ?? preset.name)",
                    kind: .preset,
                    emoji: preset.emoji ?? "🙂",
                    title: preset.name,
                    subtitle: preset.blurb ?? "\(preset.occupation.capitalized) in \(preset.town)",
                    detail: L10n.tr("\(Money.format(preset.annualIncome)) a year"),
                    badge: nil,
                    isLocked: false
                )
            )
        }
        if let random = characters?.random {
            cards.append(
                .init(
                    id: "random",
                    kind: .random,
                    emoji: "🎲",
                    title: "Random",
                    subtitle: L10n.tr("\(random.name), \(random.occupation) in \(random.town). Drawn from the UK population."),
                    detail: L10n.tr("\(Money.format(random.annualIncome)) a year"),
                    badge: nil,
                    isLocked: false
                )
            )
        }
        return CharacterSelectViewState(
            phase: phase,
            intro: L10n.tr("Live a whole life with real UK numbers. Every year you choose what to do with your money."),
            cards: cards,
            usesSampleData: usesSampleData,
            versionText: AppInfo.versionText
        )
    }
}

/// App name and version for labels.
enum AppInfo {
    static var versionText: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = info?["CFBundleVersion"] as? String ?? "1"
        return "\(Brand.productName) \(version) (\(build))"
    }
}
