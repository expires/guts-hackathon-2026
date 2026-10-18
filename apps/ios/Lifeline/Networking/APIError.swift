import Foundation
import OpenAPIRuntime

/// Errors from the Lifeline backend, mapped to user-facing text.
///
/// The backend uses one error format everywhere:
/// `{"error": {"code": "...", "message": "...", "source": "..."}}`.
enum APIError: Error, Equatable, Sendable {
    /// The backend returned the standard error body.
    case server(status: Int, code: String, message: String, source: String)
    /// The request did not reach the backend.
    case network
    /// The backend returned a status or body that the app does not expect.
    case unexpected(status: Int)
    /// The response body did not match the contract.
    case decoding

    /// Plain English text for an alert.
    /// 409 from the finance endpoints when the server has no money data for this device yet (live data mode).
    static let noFinanceDataCode = "no_finance_data"

    /// True for 409 `no_finance_data`: the user must connect their money (onboarding) first.
    var isNoFinanceData: Bool {
        if case let .server(_, code, _, _) = self { return code == Self.noFinanceDataCode }
        return false
    }

    var userMessage: String {
        switch self {
        case let .server(status, code, message, _):
            switch code {
            case "rate_limited":
                return L10n.tr("Too many tries. Try again in a moment.")
            case "unauthorized":
                return L10n.tr("Your session ended. Try again.")
            case "invalid_input":
                return L10n.tr("The game cannot start a life with these details. The character must be at least 16 in the start year. Check the details and try again.")
            case "validation_error":
                return L10n.tr("Some details are not valid. Check them and try again.")
            case APIError.rateLimitedQuietCode:
                return L10n.tr("Couldn't load. Pull to refresh.")
            case APIError.noFinanceDataCode:
                return L10n.tr("Open Life and tap Play yourself to add your job, pay and savings. Then your money shows here.")
            default:
                // Any other 429 also gets the client text, so it follows the app language (ADR 0063).
                if status == 429 { return L10n.tr("Too many tries. Try again in a moment.") }
                return message.isEmpty ? L10n.tr("Something went wrong. Try again.") : message
            }
        case .network:
            return L10n.tr("Cannot reach the \(Brand.productName) server. Check your connection and try again.")
        case let .unexpected(status):
            return L10n.tr("Something went wrong (code \(status)). Try again.")
        case .decoding:
            return L10n.tr("The server sent data the app cannot read. Update the app and try again.")
        }
    }

    /// Builds an error from a raw HTTP error body. Falls back to `.unexpected` when the body is not the standard format.
    static func from(status: Int, body: Data) -> APIError {
        if let decoded = try? JSONDecoder().decode(Components.Schemas._Error.self, from: body) {
            return .server(
                status: status,
                code: decoded.error.code,
                message: decoded.error.message,
                source: decoded.error.source
            )
        }
        return .unexpected(status: status)
    }

    /// Maps any thrown error to an `APIError`.
    static func map(_ error: any Error) -> APIError {
        if let apiError = error as? APIError { return apiError }
        if let clientError = error as? ClientError { return map(clientError.underlyingError) }
        if error is URLError { return .network }
        if error is DecodingError { return .decoding }
        return .unexpected(status: 0)
    }
}
