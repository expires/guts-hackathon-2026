import SwiftUI

/// Hidden Debug menu: switch between the live backend and canned data.
struct DebugMenuView: View {
    let state: DebugMenuViewState
    var actions: DebugMenuActions = .noop

    var body: some View {
        SheetContainer(title: "Debug", closeIdentifier: "debug.close", onClose: actions.onClose) {
            RowGroup {
                LLToggleRow(title: "Use mock data (mock client)", subtitle: state.note, isOn: state.useMockClient, identifier: "debug.useMock") {
                    actions.onToggleMock($0)
                }
            }
            VStack(alignment: .leading, spacing: Theme.Spacing.s) {
                LLTextField(title: "Demo device id", text: Binding(get: { state.demoDeviceID }, set: actions.onDemoDeviceIDChange), identifier: "debug.demoDeviceID")
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Button("Use presenter id (demo-presenter-01)", action: actions.onUsePresenterID)
                    .buttonStyle(.text)
                    .accessibilityIdentifier("debug.usePresenterID")
                if !state.demoDeviceIDIsValid {
                    Text("Use 8 to 64 letters, digits or dashes.").font(.llLabelBold)
                }
                Text("Leave empty to use this device's own id.").font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
            RowGroup(title: "Now") {
                row("Client", state.activeClient)
                row("Server", state.baseURL)
                row("Device id", state.activeDeviceID)
                row("Version", state.versionText)
            }
        }
    }

    private func row(_ title: String, _ value: String) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title).font(.llBodyBold)
            Spacer()
            Text(value).font(.llLabel).multilineTextAlignment(.trailing)
        }
        .frame(minHeight: Theme.minTarget)
        .accessibilityElement(children: .combine)
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
