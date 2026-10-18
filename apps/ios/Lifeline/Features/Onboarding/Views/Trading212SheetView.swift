import SwiftUI

/// Trading 212 key and secret (Settings, API in the Trading 212 app). Read only. The secret stays in this sheet
/// until it is sent to our server over TLS; the app never stores it.
struct Trading212SheetView: View {
    let sheet: Trading212Sheet
    let onSubmit: (_ key: String, _ secret: String) -> Void
    let onClose: () -> Void

    @State private var key = ""
    @State private var secret = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: Theme.Spacing.l) {
                HStack(spacing: Theme.Spacing.m) {
                    Text("Connect Trading 212").font(.llScreenHeader)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .accessibilityAddTraits(.isHeader)
                    HeaderSquareButton(kind: .close, identifier: "trading212.close", action: onClose)
                }
                Text("In the Trading 212 app, open Settings, then API, and create a key that can only read. Paste the key and the secret here.")
                    .font(.llBody)
                    .fixedSize(horizontal: false, vertical: true)
                LLTextField(title: L10n.tr("API key"), text: $key, identifier: "trading212.key")
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                VStack(alignment: .leading, spacing: Theme.Spacing.xs) {
                    Text("API secret").font(.llLabelBold)
                    SecureField(L10n.tr("API secret"), text: $secret)
                        .font(.llBody)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .padding(.horizontal, Theme.Spacing.m)
                        .frame(minHeight: Theme.buttonHeight)
                        .inkSurface(.buttonAlt)
                        .accessibilityIdentifier("trading212.secret")
                }
                Text("Penny only reads your balance. It cannot trade. Your key is kept encrypted on our server, never in the app.")
                    .font(.llLabel)
                    .foregroundStyle(Theme.Palette.muted)
                    .fixedSize(horizontal: false, vertical: true)
                if let message = sheet.errorMessage {
                    Text(message)
                        .font(.llBody)
                        .foregroundStyle(Theme.Palette.onArea)
                        .padding(Theme.Spacing.l)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .inkSurface(.cardAlt, fill: Theme.Palette.health)
                        .accessibilityIdentifier("trading212.error")
                }
                PrimaryButton(title: L10n.tr("Connect"), isBusy: sheet.isBusy) { onSubmit(key, secret) }
                    .disabled(sheet.isBusy || key.isEmpty || secret.isEmpty)
                    .accessibilityIdentifier("trading212.connect")
            }
            .padding(Theme.Spacing.margin)
        }
        .scrollDismissesKeyboard(.interactively)
        .paperBackground()
    }
}

#Preview("Trading 212 · light") {
    Trading212SheetView(sheet: .init(isPresented: true), onSubmit: { _, _ in }, onClose: {})
}

#Preview("Trading 212 · error · dark") {
    Trading212SheetView(
        sheet: .init(isPresented: true, errorMessage: "Trading212 did not accept those details. Check them and try again."),
        onSubmit: { _, _ in }, onClose: {}
    ).previewDark()
}
