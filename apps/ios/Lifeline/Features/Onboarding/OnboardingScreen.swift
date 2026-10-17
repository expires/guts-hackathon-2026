import AuthenticationServices
import SwiftUI
import UniformTypeIdentifiers

/// Glue for onboarding (ADR 0029, 0037). Owns `OnboardingViewModel` and the platform parts:
/// Sign in with Apple, the Monzo consent page (`ASWebAuthenticationSession`) and the statement picker.
struct OnboardingScreen: View {
    @State private var model: OnboardingViewModel
    @State private var showsPicker = false
    @Environment(\.webAuthenticationSession) private var webAuthenticationSession
    private let onFinished: @MainActor () -> Void

    init(client: any LifelineClient, startAt: OnboardingStep = .welcome, onFinished: @escaping @MainActor () -> Void) {
        self.init(api: .from(client: client), isSampleData: client.kind == .mock, startAt: startAt, onFinished: onFinished)
    }

    init(api: OnboardingAPI, isSampleData: Bool, startAt: OnboardingStep = .welcome, onFinished: @escaping @MainActor () -> Void) {
        _model = State(initialValue: OnboardingViewModel(
            api: api,
            appleAvailable: AppleSignIn.isAvailable,
            isSampleData: isSampleData,
            startAt: startAt
        ))
        self.onFinished = onFinished
    }

    var body: some View {
        OnboardingView(state: model.state, actions: model.actions)
            .onAppear(perform: wire)
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

    private func wire() {
        model.onFinished = onFinished
        model.pickStatement = { showsPicker = true }
        model.appleSignIn = { try await AppleSignIn().identityToken() }
        let session = webAuthenticationSession
        model.openBank = { url in
            try await session.authenticate(using: url, callbackURLScheme: "lifeline", preferredBrowserSession: .ephemeral)
        }
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
