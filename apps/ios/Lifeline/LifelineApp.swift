import SwiftUI

@main
struct LifelineApp: App {
    @State private var session = GameSession(client: ClientFactory.makeForLaunch())
    private let isPlayground = ClientFactory.isPlayground()

    var body: some Scene {
        WindowGroup {
            if isPlayground {
                PlaygroundScreen()
            } else {
                RootScreen(session: session)
            }
        }
    }
}
