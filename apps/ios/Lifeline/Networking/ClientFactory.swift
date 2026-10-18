import Foundation

/// Picks `LiveClient` or `MockClient` for this launch (ADR 0011).
///
/// Order of precedence:
/// 1. Launch argument `-mockClient` or `-uiTestingMock`.
/// 2. Debug builds only: UserDefaults `debug.useMockClient` (set from the hidden debug menu).
/// 3. Info.plist `LifelineClient` (build setting `LIFELINE_CLIENT`: `live` or `mock`).
enum ClientFactory {
    static let mockArguments: Set<String> = ["-mockClient", "-uiTestingMock"]
    static let playgroundArgument = "-playground"
    static let debugDefaultsKey = "debug.useMockClient"
    static let infoPlistKey = "LifelineClient"

    struct LaunchOptions: Equatable, Sendable {
        var arguments: [String]
        /// Value of `debug.useMockClient`, or nil when unset. Ignored outside Debug builds.
        var debugUseMock: Bool?
        /// Value of Info.plist `LifelineClient`.
        var infoPlistClient: String?
        var isDebugBuild: Bool
    }

    static func kind(for options: LaunchOptions) -> ClientKind {
        if options.arguments.contains(where: mockArguments.contains) { return .mock }
        if options.isDebugBuild, let useMock = options.debugUseMock { return useMock ? .mock : .live }
        if options.infoPlistClient?.lowercased() == ClientKind.mock.rawValue { return .mock }
        return .live
    }

    static func currentOptions(
        processInfo: ProcessInfo = .processInfo,
        defaults: UserDefaults = .standard,
        bundle: Bundle = .main
    ) -> LaunchOptions {
        LaunchOptions(
            arguments: processInfo.arguments,
            debugUseMock: defaults.object(forKey: debugDefaultsKey) as? Bool,
            infoPlistClient: bundle.object(forInfoDictionaryKey: infoPlistKey) as? String,
            isDebugBuild: isDebugBuild
        )
    }

    static var isDebugBuild: Bool {
        #if DEBUG
        true
        #else
        false
        #endif
    }

    /// The Playground gallery exists only in Debug builds (PENNY_V3_BUILD.md F6); the phones run Demo.
    static func isPlayground(arguments: [String] = ProcessInfo.processInfo.arguments) -> Bool {
        #if DEBUG
        arguments.contains(playgroundArgument)
        #else
        false
        #endif
    }

    static func make(_ kind: ClientKind) -> any LifelineClient {
        switch kind {
        case .mock: MockClient(data: .recorded)
        case .live: LiveClient(baseURL: LiveClient.configuredBaseURL())
        }
    }

    static func makeForLaunch() -> any LifelineClient {
        make(kind(for: currentOptions()))
    }
}
