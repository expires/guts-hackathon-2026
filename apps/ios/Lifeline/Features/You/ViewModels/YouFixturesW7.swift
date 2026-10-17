import Foundation

/// You tab fixture with lives, concepts, sources and credits (W7, ADR 0026).
@MainActor
enum YouFixturesW7 {
    static var full: YouViewState {
        YouViewModel.makeState(
            profile: ContractExamples.financeProfile,
            phase: .ready,
            clientKind: .mock,
            isDebugBuild: true,
            lives: ContractExamples.lives.lives,
            conceptsUnlocked: Fixtures.midLife.conceptsUnlocked.count,
            conceptsTotal: ContractExamples.concepts.count,
            sources: ContractExamples.sources,
            credits: CreditsFile.load()
        )
    }
}
