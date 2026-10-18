import AuthenticationServices
import SwiftUI
import UniformTypeIdentifiers

/// Glue for onboarding (ADR 0029, 0037). Owns `OnboardingViewModel` and the platform parts:
/// Sign in with Apple, the Monzo sign-in (opened in Safari) and the statement picker.
struct OnboardingScreen: View {
    @State private var model: OnboardingViewModel
    @State private var showsPicker = false
    /// "Ask Penny" on the forecast card ("Their Next Move").
    @State private var showsPenny = false
    @Environment(\.openURL) private var openURL
    @Environment(\.scenePhase) private var scenePhase
    private let onFinished: @MainActor () -> Void
    private let onLanguage: @MainActor (AppLanguage) -> Void
    /// For the open Penny chat step. Nil (tests, Playground fixtures) shows a short note instead.
    private let client: (any LifelineClient)?

    init(
        client: any LifelineClient,
        startAt: OnboardingStep = .welcome,
        onLanguage: @escaping @MainActor (AppLanguage) -> Void = { _ in },
        onFinished: @escaping @MainActor () -> Void
    ) {
        self.init(api: Self.api(for: client), isSampleData: client.kind == .mock, startAt: startAt, client: client, onLanguage: onLanguage, onFinished: onFinished)
    }

    init(
        api: OnboardingAPI,
        isSampleData: Bool,
        startAt: OnboardingStep = .welcome,
        client: (any LifelineClient)? = nil,
        onLanguage: @escaping @MainActor (AppLanguage) -> Void = { _ in },
        onFinished: @escaping @MainActor () -> Void
    ) {
        self.client = client
        self.onLanguage = onLanguage
        _model = State(initialValue: OnboardingViewModel(
            api: api,
            appleAvailable: AppleSignIn.isAvailable,
            isSampleData: isSampleData,
            startAt: startAt
        ))
        self.onFinished = onFinished
    }

    /// The live calls. Debug builds launched with `-onboardingRecorded` (UI tests, screenshots) answer from
    /// recorded responses for one sample student instead.
    private static func api(for client: any LifelineClient) -> OnboardingAPI {
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains(OnboardingRecorded.launchArgument) { return OnboardingRecorded.api }
        #endif
        return .from(client: client)
    }

    var body: some View {
        Group {
            if model.state.step == .penny {
                pennyStep
            } else {
                OnboardingView(state: model.state, actions: model.actions)
            }
        }
            .onAppear(perform: wire)
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { model.recheckMonzo() }
            }
            // `lifeline://connected?...` reaches us through RootScreen (see `OnboardingLink`).
            .onReceive(NotificationCenter.default.publisher(for: OnboardingLink.notification)) { note in
                if let url = note.object as? URL { model.handleConnectedURL(url) }
            }
            .onOpenURL { url in model.handleConnectedURL(url) }
            .sheet(isPresented: $showsPenny) {
                if let client {
                    // A new chat with the forecast loaded and "Explain my weekly budget" sent (B3.7).
                    PennyScreen(
                        client: client,
                        context: PennyContext(screen: .forecast, question: L10n.tr("Explain my weekly budget"), title: L10n.tr("My weekly budget")),
                        onClose: { showsPenny = false }
                    )
                }
            }
            .fileImporter(
                isPresented: $showsPicker,
                allowedContentTypes: [.commaSeparatedText, .pdf, .plainText],
                allowsMultipleSelection: false
            ) { result in
                guard case let .success(urls) = result, let url = urls.first else { return }
                let access = url.startAccessingSecurityScopedResource()
                defer { if access { url.stopAccessingSecurityScopedResource() } }
                guard let data = try? Data(contentsOf: url) else { return }
                let name = url.lastPathComponent
                Task { await model.importStatement(data: data, fileName: name) }
            }
    }

    /// "Try Penny" (ADR 0069): an open Penny chat (general, student and money questions, no data needed). Skip moves on.
    private var pennyStep: some View {
        VStack(spacing: 0) {
            HStack(spacing: Theme.Spacing.m) {
                HeaderSquareButton(kind: .back, identifier: "onboarding.back") { model.back() }
                Text("Try Penny").font(.llScreenHeader).frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityAddTraits(.isHeader)
                Button("Skip") { model.skip() }
                    .buttonStyle(.text)
                    .frame(minWidth: Theme.minTarget, minHeight: Theme.minTarget)
                    .contentShape(.rect)
                    .accessibilityIdentifier("onboarding.penny.skip")
            }
            .padding(.horizontal, Theme.Spacing.margin)
            .padding(.top, Theme.Spacing.s)
            .padding(.bottom, Theme.Spacing.xs)
            if let client {
                PennyScreen(client: client, context: PennyContext(screen: .onboarding), onClose: { model.next() })
            } else {
                Text("Ask Penny anything about money or student life. She answers in a sentence or two.")
                    .font(.llBody)
                    .padding(Theme.Spacing.margin)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            }
        }
        .paperBackground()
        .toolbar(.hidden, for: .navigationBar)
    }

    private func wire() {
        model.onFinished = onFinished
        // Confirm saves the app language (RootScreen switches the whole app), then tells the caller.
        model.onLanguage = { language in
            AppLanguage.set(language)
            onLanguage(language)
        }
        model.pickStatement = { showsPicker = true }
        model.onAskPenny = { if client != nil { showsPenny = true } }
        model.appleSignIn = { try await AppleSignIn().identityToken() }
        // Monzo signs in with an emailed link, so the page opens in Safari (not an in-app browser).
        let open = openURL
        model.openInSafari = { url in open(url) }
        // Location is not set up in this build (no location permission yet): the view says so.
        model.locate = nil
    }
}

/// Sign in with Apple through `ASAuthorizationController`, with our own button (no system button).
@MainActor
final class AppleSignIn: NSObject, ASAuthorizationControllerDelegate, ASAuthorizationControllerPresentationContextProviding {
    private var continuation: CheckedContinuation<String, Error>?

    /// True when the signed app has the Sign in with Apple entitlement. The simulator and builds
    /// without the capability return false, and onboarding offers the demo sign-in only.
    static var isAvailable: Bool {
        guard let url = Bundle.main.url(forResource: "embedded", withExtension: "mobileprovision"),
              let data = try? Data(contentsOf: url) else { return false }
        return String(decoding: data, as: UTF8.self).contains("com.apple.developer.applesignin")
    }

    func identityToken() async throws -> String {
        let request = ASAuthorizationAppleIDProvider().createRequest()
        request.requestedScopes = [.fullName]
        let controller = ASAuthorizationController(authorizationRequests: [request])
        controller.delegate = self
        controller.presentationContextProvider = self
        return try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
            controller.performRequests()
        }
    }

    nonisolated func authorizationController(controller: ASAuthorizationController, didCompleteWithAuthorization authorization: ASAuthorization) {
        let token = (authorization.credential as? ASAuthorizationAppleIDCredential)?.identityToken.flatMap { String(data: $0, encoding: .utf8) }
        MainActor.assumeIsolated {
            if let token {
                continuation?.resume(returning: token)
            } else {
                continuation?.resume(throwing: APIError.decoding)
            }
            continuation = nil
        }
    }

    nonisolated func authorizationController(controller: ASAuthorizationController, didCompleteWithError error: Error) {
        let sendable = error.localizedDescription
        MainActor.assumeIsolated {
            continuation?.resume(throwing: APIError.server(status: 401, code: "apple_sign_in", message: sendable, source: "apple"))
            continuation = nil
        }
    }

    nonisolated func presentationAnchor(for controller: ASAuthorizationController) -> ASPresentationAnchor {
        MainActor.assumeIsolated {
            UIApplication.shared.connectedScenes
                .compactMap { $0 as? UIWindowScene }
                .flatMap(\.windows)
                .first { $0.isKeyWindow } ?? ASPresentationAnchor()
        }
    }
}

/// How `lifeline://connected?...` gets from `RootScreen.onOpenURL` to onboarding, which is shown over it.
enum OnboardingLink {
    static let notification = Notification.Name("lifeline.onboarding.connected")

    @MainActor static func post(_ url: URL) {
        guard url.scheme == "lifeline", url.host() == "connected" else { return }
        NotificationCenter.default.post(name: notification, object: url)
    }
}
