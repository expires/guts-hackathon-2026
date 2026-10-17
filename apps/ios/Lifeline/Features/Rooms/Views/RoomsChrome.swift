// View helpers for the W9 room screens. Design system tokens and components only (ADR 0026).
import SwiftUI
import UIKit

/// Socket status line: "Reconnecting (try 2)" with an optional "Reconnect" button.
struct RoomConnectionBanner: View {
    let state: RoomConnectionState
    var onRetry: () -> Void = {}

    var body: some View {
        HStack(spacing: Theme.Spacing.m) {
            LLIconImage(state.kind == .offline ? .crash : .statusCached, size: 24)
            Text(state.text)
                .font(.llLabelBold)
                .frame(maxWidth: .infinity, alignment: .leading)
            if state.canRetry {
                Button("Reconnect", action: onRetry)
                    .buttonStyle(.text)
                    .accessibilityIdentifier("room.reconnect")
            }
        }
        .foregroundStyle(Theme.Palette.onArea)
        .padding(.horizontal, Theme.Spacing.m)
        .padding(.vertical, Theme.Spacing.s)
        .frame(minHeight: Theme.minTarget)
        .inkSurface(.badge, fill: state.kind == .offline ? Theme.Palette.health : Theme.Palette.home, lineWidth: Theme.chipOutline)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("room.connection")
    }
}

/// "Ready" (money fill), "Not ready" (dashed outline) or "Away" (grey).
struct RoomStatusChip: View {
    let text: String
    let isReady: Bool
    var isConnected = true

    var body: some View {
        if isReady {
            Chip(text: text, fill: Theme.Palette.money)
        } else if !isConnected {
            Chip(text: text, fill: Theme.Palette.other)
        } else {
            Text(text)
                .font(.llLabelBold)
                .foregroundStyle(Theme.Palette.ink)
                .padding(.horizontal, Theme.Spacing.s)
                .padding(.vertical, 2)
                .background {
                    HandCut.chip.stroke(Theme.Palette.ink, style: StrokeStyle(lineWidth: Theme.chipOutline, dash: [4, 3]))
                }
        }
    }
}

/// QR code image from PNG data, drawn without smoothing so it stays sharp.
struct RoomQRImage: View {
    let png: Data?
    var size: CGFloat = 132

    var body: some View {
        Group {
            if let png, let image = UIImage(data: png) {
                Image(uiImage: image)
                    .interpolation(.none)
                    .resizable()
                    .scaledToFit()
                    .padding(Theme.Spacing.s)
                    .background(Color.white)
            } else {
                Text("No QR code").font(.llLabel).foregroundStyle(Theme.Palette.muted)
            }
        }
        .frame(width: size, height: size)
        .inkSurface(.buttonThird, fill: Color.white, lineWidth: Theme.chipOutline)
    }
}

/// Shape of the lobby while it opens: QR block, code line, faces (ADR 0060, no spinner).
struct LobbySkeleton: View {
    var body: some View {
        VStack(spacing: Theme.Spacing.l) {
            VStack(spacing: Theme.Spacing.m) {
                LLSkeleton(.block(height: 220)).frame(width: 220)
                LLSkeleton(.line(width: 0.5, height: 32))
            }
            .frame(maxWidth: .infinity)
            .padding(Theme.Spacing.l)
            .inkSurface(.hero, lineWidth: Theme.chipOutline)
            HStack(spacing: Theme.Spacing.m) {
                ForEach(0..<4, id: \.self) { _ in LLSkeleton(.circle(diameter: 56)) }
                Spacer(minLength: 0)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Opening the lobby")
        .accessibilityIdentifier("lobby.skeleton")
    }
}
