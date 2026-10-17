import SwiftUI

@main
struct LifelineApp: App {
    @State private var session = GameSession(client: ClientFactory.makeForLaunch())
    private let isPlayground = ClientFactory.isPlayground()

    init() {
        LLAppearance.apply()
    }

    var body: some Scene {
        WindowGroup {
            Group {
                if isPlayground {
                    PlaygroundScreen()
                } else {
                    RootScreen(session: session)
                }
            }
            .font(.llBody)
            .foregroundStyle(Theme.Palette.ink)
            .tint(Theme.Palette.ink)
        }
    }
}
