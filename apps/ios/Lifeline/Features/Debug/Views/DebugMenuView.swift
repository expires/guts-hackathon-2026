import SwiftUI

/// Hidden Debug menu: switch between the live backend and canned data.
struct DebugMenuView: View {
    let state: DebugMenuViewState
    var actions: DebugMenuActions = .noop

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Toggle("Use sample data (mock client)", isOn: Binding(get: { state.useMockClient }, set: actions.onToggleMock))
                        .accessibilityIdentifier("debug.useMock")
                } footer: {
                    Text(state.note)
                }
                Section {
                    TextField("Demo device id", text: Binding(get: { state.demoDeviceID }, set: actions.onDemoDeviceIDChange))
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .accessibilityIdentifier("debug.demoDeviceID")
                    Button("Use presenter id (demo-presenter-01)", action: actions.onUsePresenterID)
                        .accessibilityIdentifier("debug.usePresenterID")
                    if !state.demoDeviceIDIsValid {
                        Text("Use 8 to 64 letters, digits or dashes.").foregroundStyle(.red)
                    }
                } header: {
                    Text("Demo sign-in")
                } footer: {
                    Text("Leave empty to use this device's own id.")
                }
                Section("Now") {
                    LabeledContent("Client", value: state.activeClient)
                    LabeledContent("Server", value: state.baseURL)
                    LabeledContent("Device id", value: state.activeDeviceID)
                    LabeledContent("Version", value: state.versionText)
                }
            }
            .navigationTitle("Debug")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done", action: actions.onClose)
                }
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Live · light") {
    DebugMenuView(state: Fixtures.Debug.live)
}

#Preview("Live · dark") {
    DebugMenuView(state: Fixtures.Debug.live).previewDark()
}

#Preview("Live · AX3") {
    DebugMenuView(state: Fixtures.Debug.live).previewLargeType()
}

#Preview("Presenter · light") {
    DebugMenuView(state: Fixtures.Debug.presenter)
}

#Preview("Presenter · dark") {
    DebugMenuView(state: Fixtures.Debug.presenter).previewDark()
}

#Preview("Presenter · AX3") {
    DebugMenuView(state: Fixtures.Debug.presenter).previewLargeType()
}
