import Foundation

/// Account calls (ADR 0029), as closures (ADR 0037). Tests pass their own closures.
struct AccountAPI: Sendable {
    var getMe: @Sendable () async throws -> Components.Schemas.Me
    var signOut: @Sendable () async throws -> Void
    var deleteAccount: @Sendable () async throws -> Void
    var resetDemo: @Sendable () async throws -> Components.Schemas.Me

    static func from(client: any LifelineClient) -> AccountAPI {
        AccountAPI(
            getMe: { try await client.getMe() },
            signOut: { try await client.signOut() },
            deleteAccount: { try await client.deleteAccount() },
            resetDemo: { try await client.resetDemo() }
        )
    }
}
