// Draft by W9. QR scanner to join a Same Life room (ADR 0029). Design system chrome around the camera.
@preconcurrency import AVFoundation
import SwiftUI
import UIKit

/// Full screen: camera in a hand-cut frame. A scanned QR text goes to `onScanned`.
struct RoomScannerView: View {
    let state: RoomScannerViewState
    var actions: RoomScannerActions = .noop

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            ScreenHeader(title: "Scan a room code", leading: HeaderSquareButton(kind: .close, identifier: "scanner.close", action: actions.onClose))
            switch state.status {
            case .asking:
                LLSkeleton(.block(height: 320))
                    .accessibilityLabel("Asking to use the camera")
            case .scanning:
                QRCameraPreview(onCode: actions.onScanned)
                    .aspectRatio(1, contentMode: .fit)
                    .clipShape(HandCut.hero)
                    .overlay { HandCut.hero.strokeBorder(Theme.Palette.ink, lineWidth: Theme.outline) }
                    .background { HandCut.hero.fill(Theme.Palette.ink).offset(x: Theme.heroShadow.width, y: Theme.heroShadow.height) }
                    .accessibilityLabel("Camera. Point it at the room QR code.")
                    .accessibilityIdentifier("scanner.camera")
                Text("Point the camera at the QR code in the other phone's lobby.")
                    .font(.llBody)
                    .fixedSize(horizontal: false, vertical: true)
            case let .unavailable(message):
                Text(message)
                    .font(.llBody)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityIdentifier("scanner.unavailable")
                Button("Type a code instead", action: actions.onTypeCode)
                    .buttonStyle(.main)
                    .accessibilityIdentifier("scanner.type")
            }
            if let hint = state.hint {
                Chip(text: hint, fill: Theme.Palette.health)
                    .accessibilityIdentifier("scanner.hint")
            }
            if case .scanning = state.status {
                Button("Type a code instead", action: actions.onTypeCode)
                    .buttonStyle(.second)
                    .accessibilityIdentifier("scanner.typeCode")
            }
            Spacer(minLength: 0)
        }
        .foregroundStyle(Theme.Palette.ink)
        .padding(.horizontal, Theme.Spacing.margin)
        .padding(.top, Theme.Spacing.m)
        .paperBackground()
    }
}

/// Camera preview that reports QR codes. Starts on appear and stops on disappear.
struct QRCameraPreview: UIViewRepresentable {
    let onCode: @MainActor (String) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onCode: onCode) }

    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView()
        view.previewLayer.videoGravity = .resizeAspectFill
        view.previewLayer.session = context.coordinator.session
        context.coordinator.configure()
        return view
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {
        context.coordinator.onCode = onCode
    }

    static func dismantleUIView(_ uiView: PreviewView, coordinator: Coordinator) {
        coordinator.stop()
    }

    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }

    final class Coordinator: NSObject, AVCaptureMetadataOutputObjectsDelegate, @unchecked Sendable {
        let session = AVCaptureSession()
        var onCode: @MainActor (String) -> Void
        private var lastCode: String?
        private let queue = DispatchQueue(label: "lifeline.rooms.scanner")

        init(onCode: @escaping @MainActor (String) -> Void) {
            self.onCode = onCode
        }

        func configure() {
            queue.async { [self] in
                guard let device = AVCaptureDevice.default(for: .video),
                      let input = try? AVCaptureDeviceInput(device: device),
                      session.canAddInput(input) else { return }
                session.beginConfiguration()
                session.addInput(input)
                let output = AVCaptureMetadataOutput()
                if session.canAddOutput(output) {
                    session.addOutput(output)
                    output.setMetadataObjectsDelegate(self, queue: .main)
                    output.metadataObjectTypes = [.qr]
                }
                session.commitConfiguration()
                session.startRunning()
            }
        }

        func stop() {
            queue.async { [self] in session.stopRunning() }
        }

        nonisolated func metadataOutput(_ output: AVCaptureMetadataOutput, didOutput metadataObjects: [AVMetadataObject], from connection: AVCaptureConnection) {
            guard let code = (metadataObjects.first as? AVMetadataMachineReadableCodeObject)?.stringValue else { return }
            MainActor.assumeIsolated {
                guard code != lastCode else { return }
                lastCode = code
                onCode(code)
            }
        }
    }
}

// MARK: - Previews (one per fixture: light, dark, AX3 Dynamic Type)

#Preview("Unavailable · light") { RoomScannerView(state: RoomFlowFixtures.scannerUnavailable) }
#Preview("Unavailable · dark") { RoomScannerView(state: RoomFlowFixtures.scannerUnavailable).previewDark() }
#Preview("Unavailable · AX3") { RoomScannerView(state: RoomFlowFixtures.scannerUnavailable).previewLargeType() }
#Preview("Bad code · light") { RoomScannerView(state: .init(status: .unavailable("Camera preview is off in previews."), hint: "That QR code is not a \(Brand.productName) room.")) }
