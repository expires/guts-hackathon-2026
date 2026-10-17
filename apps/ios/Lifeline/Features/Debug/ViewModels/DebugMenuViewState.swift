import Foundation

struct DebugMenuViewState: Equatable, Sendable {
    /// Value of UserDefaults `debug.useMockClient`. Takes effect on next launch.
    var useMockClient: Bool
    /// Client in use now: "live" or "mock".
    var activeClient: String
    var baseURL: String
    /// Debug override for the demo sign-in device id. Empty = no override.
    var demoDeviceID: String
    /// Device id in use now.
    var activeDeviceID: String
    /// False when `demoDeviceID` is not empty and not a valid id.
    var demoDeviceIDIsValid: Bool
    var versionText: String
    var note: String
}

struct DebugMenuActions {
    var onToggleMock: @MainActor (Bool) -> Void = { _ in }
    var onDemoDeviceIDChange: @MainActor (String) -> Void = { _ in }
    /// Sets the override to `demo-presenter-01` (the `make demo-seed` id).
    var onUsePresenterID: @MainActor () -> Void = {}
    var onClose: @MainActor () -> Void = {}

    static var noop: Self { .init() }
}
