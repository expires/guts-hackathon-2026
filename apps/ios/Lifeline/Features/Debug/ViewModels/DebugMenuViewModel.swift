import Foundation
import Observation

/// Hidden Debug-only menu. Long-press the version label on character select to open it.
@MainActor
@Observable
final class DebugMenuViewModel {
    private let defaults: UserDefaults
    private let activeKind: ClientKind
    private(set) var useMockClient: Bool
    private(set) var demoDeviceID: String

    static let presenterDeviceID = "demo-presenter-01"
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(activeKind: ClientKind, defaults: UserDefaults = .standard) {
        self.activeKind = activeKind
        self.defaults = defaults
        self.useMockClient = defaults.bool(forKey: ClientFactory.debugDefaultsKey)
        self.demoDeviceID = defaults.string(forKey: DeviceIdentity.debugOverrideKey) ?? ""
    }

    var state: DebugMenuViewState {
        DebugMenuViewState(
            useMockClient: useMockClient,
            activeClient: activeKind.rawValue,
            baseURL: LiveClient.configuredBaseURL().absoluteString,
            demoDeviceID: demoDeviceID,
            activeDeviceID: DeviceIdentity.current(defaults: defaults),
            demoDeviceIDIsValid: demoDeviceID.isEmpty || DeviceIdentity.isValid(demoDeviceID),
            versionText: AppInfo.versionText,
            note: "Changes apply on the next launch. Launch arguments -mockClient, -uiTestingMock and -demoDeviceID always win."
        )
    }

    var actions: DebugMenuActions {
        DebugMenuActions(
            onToggleMock: { [weak self] in self?.setUseMock($0) },
            onDemoDeviceIDChange: { [weak self] in self?.setDemoDeviceID($0) },
            onUsePresenterID: { [weak self] in self?.setDemoDeviceID(Self.presenterDeviceID) },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    /// Saves the override only when it is valid. An empty value removes it.
    func setDemoDeviceID(_ value: String) {
        let trimmed = value.trimmingCharacters(in: .whitespaces)
        demoDeviceID = trimmed
        if trimmed.isEmpty {
            defaults.removeObject(forKey: DeviceIdentity.debugOverrideKey)
        } else if DeviceIdentity.isValid(trimmed) {
            defaults.set(trimmed, forKey: DeviceIdentity.debugOverrideKey)
        }
    }

    func setUseMock(_ value: Bool) {
        useMockClient = value
        defaults.set(value, forKey: ClientFactory.debugDefaultsKey)
    }
}
