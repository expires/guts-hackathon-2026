import Foundation
import HTTPTypes
import OpenAPIRuntime

/// Supplies a bearer token. Implementations cache the token and refresh it on demand.
protocol TokenProviding: Sendable {
    func token() async throws -> String
    func invalidate() async
}

/// Adds `Authorization: Bearer <jwt>` to every authenticated operation.
/// On a 401 response it gets a new token and retries the request one time.
struct AuthMiddleware: ClientMiddleware {
    /// Operations that the contract marks with `security: []`.
    static let publicOperations: Set<String> = [
        "getHealth", "listSources", "signInWithApple", "signInDemo", "bankCallback",
    ]

    let tokens: any TokenProviding

    func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        guard !Self.publicOperations.contains(operationID) else {
            return try await next(request, body, baseURL)
        }
        var authorized = request
        authorized.headerFields[.authorization] = "Bearer \(try await tokens.token())"
        let (response, responseBody) = try await next(authorized, body, baseURL)
        guard response.status.code == 401 else { return (response, responseBody) }

        await tokens.invalidate()
        var retried = request
        retried.headerFields[.authorization] = "Bearer \(try await tokens.token())"
        return try await next(retried, body, baseURL)
    }
}

/// Converts every 4xx and 5xx response into a thrown `APIError`.
/// The generated client then only returns success cases.
struct ErrorMappingMiddleware: ClientMiddleware {
    static let maxErrorBodyBytes = 64 * 1024

    func intercept(
        _ request: HTTPRequest,
        body: HTTPBody?,
        baseURL: URL,
        operationID: String,
        next: @Sendable (HTTPRequest, HTTPBody?, URL) async throws -> (HTTPResponse, HTTPBody?)
    ) async throws -> (HTTPResponse, HTTPBody?) {
        let (response, responseBody) = try await next(request, body, baseURL)
        guard response.status.code >= 400 else { return (response, responseBody) }
        var data = Data()
        if let responseBody {
            data = (try? await Data(collecting: responseBody, upTo: Self.maxErrorBodyBytes)) ?? Data()
        }
        throw APIError.from(status: response.status.code, body: data)
    }
}
