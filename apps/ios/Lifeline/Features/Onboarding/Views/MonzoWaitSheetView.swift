import SwiftUI

/// The pop-up shown while Monzo sign-in runs in Safari, while the user approves in the Monzo app, and while
/// the history imports. Only its buttons close it.
struct MonzoWaitSheetView: View {
    let wait: MonzoWait
    let onReopen: () -> Void
    let onCancel: () -> Void
    let onRetry: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Spacing.l) {
            Text(title).font(.llScreenHeader)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            if let body = bodyText {
                Text(body).font(.llBody).fixedSize(horizontal: false, vertical: true)
            }
            if showsProgress {
                HStack(spacing: Theme.Spacing.m) {
                    ProgressView()
                    Text(progressLabel).font(.llLabel).foregroundStyle(Theme.Palette.muted)
                }
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("onboarding.monzo.waiting")
            }
            Spacer(minLength: 0)
            buttons
        }
        .padding(Theme.Spacing.margin)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .paperBackground()
        .accessibilityIdentifier("onboarding.monzo.sheet")
    }

    @ViewBuilder private var buttons: some View {
        switch wait {
        case .signingIn:
            PrimaryButton(title: L10n.tr("Open Safari again"), action: onReopen)
                .accessibilityIdentifier("onboarding.monzo.reopen")
            cancelButton(L10n.tr("Cancel"))
        case .approving:
            cancelButton(L10n.tr("Cancel"))
        case .importing:
            EmptyView()
        case .failed:
            PrimaryButton(title: L10n.tr("Try again"), action: onRetry)
                .accessibilityIdentifier("onboarding.monzo.retry")
            cancelButton(L10n.tr("Close"))
        }
    }

    private func cancelButton(_ title: String) -> some View {
        Button(title, action: onCancel)
            .buttonStyle(.second)
            .accessibilityIdentifier("onboarding.monzo.cancel")
    }

    private var title: String {
        switch wait {
        case .signingIn: L10n.tr("Finish signing in to Monzo")
        case .approving: L10n.tr("Approve in your Monzo app")
        case .importing: L10n.tr("Importing your Monzo history")
        case .failed: L10n.tr("Monzo was not connected")
        }
    }

    private var bodyText: String? {
        switch wait {
        case .signingIn:
            L10n.tr("Safari is open. Enter your email, open Monzo's email on this iPhone and paste the link into the same Safari tab. When you see 'Monzo connected', tap Open Penny or come back here.")
        case .approving: L10n.tr("Monzo will ask you to allow access. We check every few seconds.")
        case .importing: nil
        case let .failed(message): message
        }
    }

    private var showsProgress: Bool {
        if case .failed = wait { return false }
        return true
    }

    private var progressLabel: String {
        switch wait {
        case .signingIn: L10n.tr("Waiting for Monzo")
        case .approving: L10n.tr("Waiting for your approval")
        default: L10n.tr("Importing")
        }
    }
}

#Preview("Signing in") {
    MonzoWaitSheetView(wait: .signingIn, onReopen: {}, onCancel: {}, onRetry: {})
}

#Preview("Failed") {
    MonzoWaitSheetView(wait: .failed("Monzo has not shared your history yet."), onReopen: {}, onCancel: {}, onRetry: {})
}
