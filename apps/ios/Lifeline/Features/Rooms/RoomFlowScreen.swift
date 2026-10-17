import AVFoundation
import SwiftUI

/// Glue for a Same Life room: lobby, live room, results. Presented full screen while a room is open.
struct RoomFlowScreen: View {
    @Bindable var model: RoomFlowViewModel
    /// Closes the cover. The room stays open until the player leaves.
    var onClose: @MainActor () -> Void = {}
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Group {
            switch model.stage {
            case .entry:
                RoomHubEntry(model: model, onClose: onClose)
            case .lobby:
                if let state = model.lobbyState {
                    RoomLobbyView(state: state, actions: model.lobbyActions)
                }
            case .quiz:
                if let state = model.quizState {
                    QuizView(state: state, actions: model.roundActions)
                }
            case .decision:
                if let state = model.decisionState {
                    DecisionView(state: state, actions: model.roundActions)
                }
            case .live:
                if let state = model.liveState {
                    RoomLiveView(state: state, actions: model.liveActions)
                }
            case .results:
                if let state = model.resultState {
                    RoomResultView(state: state, actions: model.resultActions)
                }
            case .gameOver:
                if let state = model.gameOverState {
                    GameOverView(state: state, actions: model.gameOverActions)
                }
            }
        }
        .animation(Motion.standard(reduceMotion: reduceMotion), value: model.stage)
        .task(id: model.resultsKey) {
            if model.stage == .results { await model.refreshResults() }
        }
        .task(id: model.stage) {
            if model.stage == .results { await model.refreshResults() }
        }
        .task { await model.loadPaths() }
        .llCover(isPresented: $model.showsGamePicker) {
            GamePickerView(state: model.pickerState, actions: model.pickerActions)
        }
    }
}

/// Full-screen entry (character select "Rooms", deep link while no room is open).
struct RoomHubEntry: View {
    let model: RoomFlowViewModel
    var onClose: @MainActor () -> Void = {}

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                ScreenHeader(title: "Same Life", leading: HeaderSquareButton(kind: .back, identifier: "room.close", action: onClose)) {
                    if model.isSampleData { DemoDataBadge() }
                }
                RoomEntryContent(state: model.entryState, actions: model.entryActions)
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.m)
            .padding(.bottom, Theme.Spacing.xxl)
        }
        .paperBackground()
        .roomScanner(model: model)
    }
}

/// Keeps the room in step with the app: progress after each AGE (also from the Life tab),
/// and a re-join with `player_id` when the app returns from the background.
struct RoomObservers: ViewModifier {
    let model: RoomFlowViewModel
    @Environment(\.scenePhase) private var scenePhase

    func body(content: Content) -> some View {
        content
            .onChange(of: model.lifeKey) { Task { await model.lifeChanged() } }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { Task { await model.appBecameActive() } }
            }
    }
}

/// Presents the QR scanner and the "Type a code instead" screen, each full screen.
struct RoomScannerPresenter: ViewModifier {
    @Bindable var model: RoomFlowViewModel

    func body(content: Content) -> some View {
        content
            .llCover(isPresented: $model.showsScanner) {
                RoomScannerScreen(model: model)
            }
            .background {
                Color.clear.llCover(isPresented: $model.showsCodeEntry) {
                    RoomCodeEntryView(state: model.entryState, actions: model.codeEntryActions) { model.showsCodeEntry = false }
                }
            }
    }
}

extension View {
    func roomObservers(_ model: RoomFlowViewModel) -> some View { modifier(RoomObservers(model: model)) }
    func roomScanner(model: RoomFlowViewModel) -> some View { modifier(RoomScannerPresenter(model: model)) }
}

/// Glue for the scanner: camera permission, then `RoomScannerView`.
struct RoomScannerScreen: View {
    let model: RoomFlowViewModel
    @State private var status: RoomScannerViewState.Status = .asking

    var body: some View {
        RoomScannerView(state: .init(status: status, hint: model.scannerHintText), actions: model.scannerActions)
            .task { status = await Self.cameraStatus() }
    }

    /// Checks the Info.plist usage text, a camera, and the permission, in this order.
    static func cameraStatus() async -> RoomScannerViewState.Status {
        guard Bundle.main.object(forInfoDictionaryKey: "NSCameraUsageDescription") != nil else {
            return .unavailable("The camera is not set up in this build. Type the room code instead.")
        }
        guard AVCaptureDevice.default(for: .video) != nil else {
            return .unavailable("This device has no camera. Type the room code instead.")
        }
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            return .scanning
        case .notDetermined:
            return await AVCaptureDevice.requestAccess(for: .video)
                ? .scanning
                : .unavailable("Camera access is off. Type the room code instead.")
        default:
            return .unavailable("Camera access is off. Turn it on in Settings, or type the room code.")
        }
    }
}
