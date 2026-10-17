import Foundation
import Testing
@testable import Lifeline

@Suite("Client selection (ADR 0011)")
struct ClientSelectionTests {
    private func options(_ args: [String] = [], debug: Bool? = nil, plist: String? = "live", isDebug: Bool = true) -> ClientFactory.LaunchOptions {
        .init(arguments: args, debugUseMock: debug, infoPlistClient: plist, isDebugBuild: isDebug)
    }

    @Test func launchArgumentsWin() {
        #expect(ClientFactory.kind(for: options(["-mockClient"], debug: false)) == .mock)
        #expect(ClientFactory.kind(for: options(["-uiTestingMock"], debug: false, plist: "live")) == .mock)
    }

    @Test func debugToggleBeatsInfoPlist() {
        #expect(ClientFactory.kind(for: options(debug: true, plist: "live")) == .mock)
        #expect(ClientFactory.kind(for: options(debug: false, plist: "mock")) == .live)
    }

    @Test func debugToggleIgnoredInRelease() {
        #expect(ClientFactory.kind(for: options(debug: true, plist: "live", isDebug: false)) == .live)
    }

    @Test func infoPlistDecidesLast() {
        #expect(ClientFactory.kind(for: options(plist: "mock")) == .mock)
        #expect(ClientFactory.kind(for: options(plist: "live")) == .live)
        #expect(ClientFactory.kind(for: options(plist: nil)) == .live)
    }

    @Test func playgroundArgument() {
        #expect(ClientFactory.isPlayground(arguments: ["-playground"]))
        #expect(!ClientFactory.isPlayground(arguments: []))
    }
}

@Suite("Demo device id override")
struct DeviceIdentityTests {
    private func freshDefaults() -> UserDefaults {
        let name = "test.\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: name)!
        defaults.removePersistentDomain(forName: name)
        return defaults
    }

    @Test func launchArgumentBeatsDebugOverrideAndStoredID() {
        let defaults = freshDefaults()
        defaults.set("stored-device-0001", forKey: DeviceIdentity.defaultsKey)
        defaults.set("debug-device-0001", forKey: DeviceIdentity.debugOverrideKey)
        let id = DeviceIdentity.current(arguments: ["app", "-demoDeviceID", "demo-presenter-01"], defaults: defaults, isDebugBuild: true)
        #expect(id == "demo-presenter-01")
    }

    @Test func debugOverrideBeatsStoredIDInDebugOnly() {
        let defaults = freshDefaults()
        defaults.set("stored-device-0001", forKey: DeviceIdentity.defaultsKey)
        defaults.set("debug-device-0001", forKey: DeviceIdentity.debugOverrideKey)
        #expect(DeviceIdentity.current(arguments: [], defaults: defaults, isDebugBuild: true) == "debug-device-0001")
        #expect(DeviceIdentity.current(arguments: [], defaults: defaults, isDebugBuild: false) == "stored-device-0001")
    }

    @Test func invalidOverridesFallThrough() {
        let defaults = freshDefaults()
        defaults.set("stored-device-0001", forKey: DeviceIdentity.defaultsKey)
        defaults.set("bad id", forKey: DeviceIdentity.debugOverrideKey)
        #expect(DeviceIdentity.current(arguments: ["-demoDeviceID", "short"], defaults: defaults, isDebugBuild: true) == "stored-device-0001")
        #expect(DeviceIdentity.current(arguments: ["-demoDeviceID"], defaults: defaults, isDebugBuild: true) == "stored-device-0001")
    }

    @Test func createsAndKeepsRandomID() {
        let defaults = freshDefaults()
        let first = DeviceIdentity.current(arguments: [], defaults: defaults, isDebugBuild: true)
        #expect(DeviceIdentity.isValid(first))
        #expect(DeviceIdentity.current(arguments: [], defaults: defaults, isDebugBuild: true) == first)
    }

    @MainActor
    @Test func debugMenuSavesOnlyValidOverride() {
        let defaults = freshDefaults()
        let model = DebugMenuViewModel(activeKind: .live, defaults: defaults)
        model.actions.onUsePresenterID()
        #expect(defaults.string(forKey: DeviceIdentity.debugOverrideKey) == "demo-presenter-01")
        #expect(model.state.activeDeviceID == "demo-presenter-01")
        model.setDemoDeviceID("bad id")
        #expect(!model.state.demoDeviceIDIsValid)
        #expect(defaults.string(forKey: DeviceIdentity.debugOverrideKey) == "demo-presenter-01")
        model.setDemoDeviceID("")
        #expect(defaults.string(forKey: DeviceIdentity.debugOverrideKey) == nil)
    }
}
